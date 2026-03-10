import requests
import json
import numpy as np
import cv2

class ESP32Camera:
    def __init__(self, ip_address="192.168.1.100"):
        self.ip_address = ip_address
        self.capture_url = f"http://{ip_address}/capture"

    def get_frame(self):
        """ Fetch the current frame from ESP32-CAM and return it as unparsed cv2 object """
        try:
            response = requests.get(self.capture_url, timeout=2)
            if response.status_code == 200:
                img_array = np.array(bytearray(response.content), dtype=np.uint8)
                img = cv2.imdecode(img_array, -1)
                return img
            else:
                return None
        except Exception as e:
            return None
