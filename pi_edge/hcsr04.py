import RPi.GPIO as GPIO
import time

TRIG, ECHO = 23, 24
BASELINE_CM = 25.0  # flat road calibration distance (set during install)

# Initialize GPIO
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)

def get_raw_distance():
    try:
        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)
        
        timeout = time.time() + 0.04  # 40ms max (approx 7m max range)
        pulse_start = time.time()
        pulse_end = time.time()
        
        while GPIO.input(ECHO) == 0:
            pulse_start = time.time()
            if time.time() > timeout: return None
            
        while GPIO.input(ECHO) == 1:
            pulse_end = time.time()
            if time.time() > timeout: return None
            
        return ((pulse_end - pulse_start) * 34300) / 2
    except Exception as e:
        return None

def get_depth_hcsr04():
    raw = get_raw_distance()
    if raw is None: return None
    depth = raw - BASELINE_CM
    # If the depth is positive, it's a pothole. If negative, it's a bump.
    return round(depth, 1)

def cleanup():
    GPIO.cleanup()
