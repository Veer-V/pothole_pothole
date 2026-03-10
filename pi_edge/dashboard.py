import eventlet
eventlet.monkey_patch()

import time
import cv2
import threading
import logging
from flask import Flask, render_template, Response, send_file
from flask_socketio import SocketIO
from depth_fusion import DepthFusion
from camera_esp32 import ESP32Camera
from scanner_3d import Scanner3D

app = Flask(__name__)
# Async mode eventlet allows high performance websockets on python
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Global system states
SYSTEM_RUNNING = False
LATEST_FRAME = None
DEVICE_ID = 'RASPBERRY_PI_001'
POLL_HZ = 15
THRESHOLD_CM = 5.0

df = DepthFusion(use_mock=False)
cam = ESP32Camera(stream_url="http://192.168.149.173:81/stream") 
scanner = Scanner3D()

def sensor_thread():
    """ Runs in the background gathering sensor data and pushing it over WebSockets """
    global LATEST_FRAME, SYSTEM_RUNNING
    
    baseline_depth = 0.0
    calibrating = True
    calibration_samples = []

    while SYSTEM_RUNNING:
        try:
            current_depth_cm, depth_src = df.get_fused_depth()
            
            # Calibration Phase
            if calibrating:
                if current_depth_cm > 0:
                    calibration_samples.append(current_depth_cm)
                if len(calibration_samples) >= 40:
                    baseline_depth = sum(calibration_samples) / 40
                    calibrating = False
                    logging.info(f"Calibration Complete. Baseline: {baseline_depth:.2f} cm")
                time.sleep(1 / POLL_HZ)
                continue

            if current_depth_cm > 0:
                relative_depth = current_depth_cm - baseline_depth
                scanner.add_reading(relative_depth)
                
                # Emit live data to the frontend chart
                socketio.emit('sensor_data', {
                    'relative_depth': relative_depth,
                    'source': depth_src
                })
                
                # Anomaly checking
                if abs(relative_depth) >= THRESHOLD_CM:
                    logging.info(f"Anomaly! Depth: {relative_depth:.2f}cm")
                    
                    frame = cam.get_frame()
                    img_available = False
                    if frame is not None:
                        LATEST_FRAME = frame
                        img_path = f"scans_3d/anomaly_{int(time.time())}.jpg"
                        cv2.imwrite(img_path, frame)
                        img_available = True
                    
                    # Generate 3D Object
                    scanner.generate_3d_model(event_type="anomaly")
                    
                    # Push anomaly event to dashboard UI
                    socketio.emit('anomaly', {
                        'depth': relative_depth,
                        'source': depth_src,
                        'time': time.strftime("%H:%M:%S"),
                        'image_available': img_available
                    })
                    
                    # Cooldown
                    time.sleep(1.5)
            
            time.sleep(1 / POLL_HZ)
            
        except Exception as e:
            logging.error(f"Sensor loop error: {e}")
            time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

def start_server():
    global SYSTEM_RUNNING
    SYSTEM_RUNNING = True
    
    # Start the hardware background thread
    socketio.start_background_task(sensor_thread)
    
    # Start Flask Server
    logging.info("Starting Dashboard Server at http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    start_server()
