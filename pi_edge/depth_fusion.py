import logging
from tf_luna import TFLuna
from hcsr04 import get_depth_hcsr04, setup_gpio

# Set up logging for edge device
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DepthFusion:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        if not use_mock:
            setup_gpio()
            try:
                self.luna = TFLuna(port='/dev/ttyUSB0')  # Defaulting to USB TTL since Pi hardware UART is often busy
            except Exception as e:
                logging.error(f"Could not connect to TF-Luna. Detail: {e}")
                self.luna = None

    def get_fused_depth(self):
        """
        Returns: (depth_cm: float, source: str)
        source: 'lidar_luna' | 'ultrasonic_backup'
        """
        if self.use_mock:
            return 0.0, 'mock_sensor'

        # Attempt to read from primary TF-Luna
        d_luna = None
        if self.luna:
            d_luna = self.luna.read_distance()

        if d_luna is not None:
            # TF-Luna available
            return round(d_luna, 2), 'lidar_luna'
        
        # Fallback to HC-SR04
        logging.warning('LiDAR offline/invalid data — switching to HC-SR04 backup')
        depth_sr04 = get_depth_hcsr04()
        
        if depth_sr04 is not None:
            return depth_sr04, 'ultrasonic_backup'
            
        # Both failed
        return 0.0, 'none'
