import cv2
import logging
import time

class ESP32Camera:
    def __init__(self, stream_url="http://192.168.149.173:81/stream"):
        self.stream_url = stream_url
        self.cap = None

    def get_frame(self):
        """ Grabs a single frame from the live video stream. """
        try:
            # Open the stream if not already open
            if self.cap is None or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.stream_url)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Reduce lag
                
            ret, frame = self.cap.read()
            if ret:
                return frame
            else:
                logging.warning("Failed to grab frame from stream.")
                self.cap.release()
                self.cap = None
                return None
        except Exception as e:
            logging.error(f"Camera stream error: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            return None
