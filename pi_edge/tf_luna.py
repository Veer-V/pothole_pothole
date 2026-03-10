import serial
import time

class TFLuna:
    HEADER = 0x59  # TF-Luna frame header byte

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        # Using ttyUSB0 or ttyS0 depending on how it's connected to Pi
        self.ser = serial.Serial(port, baudrate, timeout=0.1)
        self.last_valid = None

    def read_distance(self):
        """ Returns distance in cm, or None on error """
        try:
            # Sync to frame start (two consecutive 0x59 bytes)
            while True:
                if self.ser.read(1)[0] == self.HEADER:
                    if self.ser.read(1)[0] == self.HEADER:
                        break
            
            frame = self.ser.read(7)  # read remaining 7 bytes
            dist_low, dist_high = frame[0], frame[1]
            distance_cm = (dist_high << 8) | dist_low
            
            # Validate checksum
            checksum = (self.HEADER * 2 + sum(frame[:8])) & 0xFF
            if len(frame) >= 8 and checksum != frame[8]:
                return None
                
            self.last_valid = distance_cm
            return distance_cm
        except Exception as e:
            return None  # Caller will trigger fallback

    def is_healthy(self):
        return self.read_distance() is not None
