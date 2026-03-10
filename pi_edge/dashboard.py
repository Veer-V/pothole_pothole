import eventlet
eventlet.monkey_patch()

import time
import cv2
import threading
import logging
import numpy as np
from collections import deque
from flask import Flask, render_template, Response, send_file
from flask_socketio import SocketIO

from depth_fusion import DepthFusion
from camera_esp32 import ESP32Camera

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- Globals mirroring the original Streamlit state ---
SYSTEM_RUNNING = False
LATEST_FRAME = None
POLL_HZ = 50 # Run sensor logic fast, UI updates at 10Hz
UI_INTERVAL = 0.10

WINDOW_SIZE = 20
BASELINE_WINDOW = 20
MAX_PLAUSIBLE = 60.0
POT_THRESH = 1.0
BUMP_THRESH = 1.0
DEEP_THRESH_CM = 8.0
CONFIRM_N = 1
COOLDOWN_S = 0.6

CLASS_LABELS = {0: "🟢 Flat Road", 1: "🟡 Shallow Pothole",
                2: "🔴 Deep Pothole", 3: "🔶 Speed Bump"}
IS_POTHOLE   = {0: False, 1: True,  2: True,  3: False}
IS_BUMP      = {0: False, 1: False, 2: False, 3: True}

SEVERITY_BANDS = [
    (0,   3,   "— Noise"),
    (3,   8,   "⚠️ Shallow"),
    (8,  15,   "🔶 Moderate"),
    (15, 999,  "🔴 Deep/Dangerous"),
]

def severity_label(depth_cm):
    for lo, hi, label in SEVERITY_BANDS:
        if lo <= depth_cm < hi:
            return label
    return "—"

def rule_classify(dist_buf, baseline, max_plausible):
    if len(dist_buf) < 2: return 0
    recent_devs = np.array(dist_buf[-2:]) - baseline
    
    if np.any(np.abs(recent_devs) > max_plausible): return 0
    if np.any((recent_devs >= -BUMP_THRESH) & (recent_devs <= POT_THRESH)): return 0
    if np.all(recent_devs < -BUMP_THRESH): return 3
    if np.all(recent_devs > DEEP_THRESH_CM): return 2
    if np.all(recent_devs > POT_THRESH): return 1
    return 0

def compute_dimensions(dist_buf, baseline):
    arr = np.array(dist_buf, dtype=float)
    dev = arr - baseline
    depth_cm = float(max(abs(dev.min()), dev.max()))
    in_anomaly  = int(np.sum((dev > POT_THRESH) | (dev < -BUMP_THRESH)))
    dist_per_reading = (30 * 100_000) / 3600 / 100.0 # 30km/h at 100hz approx
    length = round(in_anomaly * dist_per_reading, 1)
    
    return {
        "depth_cm"    : round(depth_cm, 1),
        "length_cm"   : length,
        "width_cm"    : round(length * 0.8, 1),
        "severity"    : severity_label(depth_cm),
    }

# Hardware
df = DepthFusion(use_mock=False)
cam = ESP32Camera(stream_url="http://192.168.149.173:81/stream") 

def sensor_thread():
    global SYSTEM_RUNNING
    
    dist_history = deque(maxlen=500)
    dev_history = deque(maxlen=500)
    baseline_hist = deque(maxlen=500)
    
    rolling_baseline_buf = deque(maxlen=BASELINE_WINDOW)
    
    dist_buf = []
    
    calibrated = False
    recalib_streak = 0
    baseline_cm = 0.0
    
    confirm_streak = 0
    pothole_count = 0
    bump_count = 0
    last_detect_t = 0.0
    last_depth = 0.0
    last_ui_t = 0.0

    while SYSTEM_RUNNING:
        try:
            now = time.monotonic()
            dist, depth_src = df.get_fused_depth()
            
            if dist is None or dist <= 0:
                time.sleep(1/POLL_HZ)
                continue

            # Base lining
            if not calibrated:
                rolling_baseline_buf.append(dist)
                if len(rolling_baseline_buf) == BASELINE_WINDOW:
                    baseline_cm = float(np.mean(rolling_baseline_buf))
                    calibrated = True
                    recalib_streak = 0
                    logging.info(f"Calibration Complete. Baseline: {baseline_cm:.2f} cm")
            
            if not calibrated:
                time.sleep(1/POLL_HZ)
                continue

            dev = dist - baseline_cm
            
            # Recalibration logic
            if abs(dev) > MAX_PLAUSIBLE:
                recalib_streak += 1
                if recalib_streak >= 50:
                    logging.warning("Massive shift detected. Recalibrating...")
                    calibrated = False
                    rolling_baseline_buf.clear()
                    recalib_streak = 0
                    continue
            else:
                recalib_streak = 0

            dist_history.append(dist)
            dev_history.append(dev)
            baseline_hist.append(baseline_cm)
            
            dist_buf.append(dist)
            if len(dist_buf) > WINDOW_SIZE: dist_buf.pop(0)

            final_cls = rule_classify(dist_buf, baseline_cm, MAX_PLAUSIBLE)
            
            is_ph   = IS_POTHOLE.get(final_cls, False)
            is_bump = IS_BUMP.get(final_cls, False)

            if is_ph or is_bump:
               confirm_streak += 1
            else:
               confirm_streak = 0

            if confirm_streak >= CONFIRM_N:
                elapsed = now - last_detect_t
                if elapsed >= COOLDOWN_S:
                    # FIRE ALERT
                    dims = compute_dimensions(dist_buf, baseline_cm)
                    
                    if is_ph:   pothole_count += 1
                    elif is_bump: bump_count += 1
                        
                    last_depth = dims["depth_cm"]
                    confirm_streak = 0
                    last_detect_t = now
                    
                    half = len(dist_buf) // 2
                    dist_buf[:] = dist_buf[half:]

                    log_entry = {
                        "Time"       : time.strftime("%H:%M:%S"),
                        "Type"       : CLASS_LABELS[final_cls],
                        "Dev"        : f"{dev:+.1f} cm",
                        "Depth"      : f"{dims['depth_cm']} cm",
                        "Severity"   : dims["severity"],
                        "Source"     : depth_src
                    }
                    
                    socketio.emit('anomaly', log_entry)

            # UI Throttling
            if now - last_ui_t >= UI_INTERVAL:
                socketio.emit('ui_state', {
                    'dist': dist,
                    'baseline': round(baseline_cm, 1),
                    'dev': round(dev, 1),
                    'potholes': pothole_count,
                    'bumps': bump_count,
                    'last_depth': last_depth,
                    'status': CLASS_LABELS[final_cls],
                    'source': depth_src,
                    'dev_hist': list(dev_history)[-100:] # Send last 100 devs for graph
                })
                last_ui_t = now

            time.sleep(1/POLL_HZ)
            
        except Exception as e:
            logging.error(f"Sensor loop error: {e}")
            time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

def start_server():
    global SYSTEM_RUNNING
    SYSTEM_RUNNING = True
    socketio.start_background_task(sensor_thread)
    logging.info("Starting Dashboard Server at http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    start_server()
