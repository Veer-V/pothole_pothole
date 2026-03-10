import time
import json
import logging
import cv2
from depth_fusion import DepthFusion
from camera_esp32 import ESP32Camera
from scanner_3d import Scanner3D
from tf_luna import TFLuna

# Main orchestrator script for the edge device
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')

DEVICE_ID = 'RASPBERRY_PI_001'
POLL_HZ   = 20
THRESHOLD_CM = 5.0  # Detection threshold: deviation > 5cm means pothole/bump

def classify_severity(depth_cm, width_cm):
    score = (abs(depth_cm) / 5) + (width_cm / 20)
    return min(5, max(1, int(score)))

def main():
    logging.info("Starting SmartRoad Edge v2.0 - 3D Scanner Edition")
    
    # Initialize components
    df = DepthFusion(use_mock=False)
    cam = ESP32Camera(ip_address="192.168.4.1") # Replace with ESP32 IP
    scanner = Scanner3D()

    baseline_depth = 0.0
    calibrating = True
    calibration_samples = []

    try:
        while True:
            # 1. Read Distance
            current_depth_cm, depth_src = df.get_fused_depth()
            
            # Calibration Phase (first 2 seconds)
            if calibrating:
                if current_depth_cm > 0:
                    calibration_samples.append(current_depth_cm)
                if len(calibration_samples) >= 40:
                    baseline_depth = sum(calibration_samples) / 40
                    calibrating = False
                    logging.info(f"Calibration Complete. Baseline: {baseline_depth:.2f} cm")
                time.sleep(1 / POLL_HZ)
                continue

            # Calculate relative depth (Pothole = positive diff, Bump = negative diff)
            if current_depth_cm > 0:
                relative_depth = current_depth_cm - baseline_depth
                scanner.add_reading(relative_depth)
                
                # Check anomaly
                if abs(relative_depth) >= THRESHOLD_CM:
                    logging.info(f"Anomaly Detected! Depth: {relative_depth:.2f}cm Source: {depth_src}")
                    
                    # Capture Image from ESP32-CAM
                    frame = cam.get_frame()
                    if frame is not None:
                        img_path = f"scans_3d/anomaly_{int(time.time())}.jpg"
                        cv2.imwrite(img_path, frame)
                        logging.info(f"Image Captured: {img_path}")
                    
                    # Generate 3D Object
                    scanner.generate_3d_model(event_type="anomaly")
                    
                    # Simulate cooldown so we don't trigger 100 times on the same pothole
                    time.sleep(1.5)
            
            time.sleep(1 / POLL_HZ)

    except KeyboardInterrupt:
        logging.info("Shutting down...")

if __name__ == "__main__":
    main()
