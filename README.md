# SmartRoad Pothole System v2.0 - 3D Scanner Edition

This repository contains the complete firmware and Edge device software for the SmartRoad Pothole Detection System, optimized for a Raspberry Pi 4, TF-Luna LiDAR, HC-SR04 Ultrasonic Sensor, and ESP32-CAM.

## 1. Hardware Required
*   **Raspberry Pi 4** (Running Raspberry Pi OS)
*   **TF-Luna LiDAR Module**
*   **HC-SR04 Ultrasonic Sensor** (with a 1kΩ & 2kΩ voltage divider resistor logic for Pi safety)
*   **AI-Thinker ESP32-CAM Module**

## 2. Wiring

### TF-Luna (UART Mode)
*   `VCC` -> Pi 5V (Pin 2)
*   `GND` -> Pi GND (Pin 6)
*   `TX`  -> Pi RX (GPIO 15 / Pin 10)
*   `RX`  -> Pi TX (GPIO 14 / Pin 8)

*Note: You must disable the Serial Login Shell on the Pi using `sudo raspi-config` -> Interface Options -> Serial Port -> Login Shell: No, Hardware: Yes.*

### HC-SR04 Backup
*   `VCC` -> Pi 5V
*   `GND` -> Pi GND
*   `TRIG` -> Pi GPIO 23 (Pin 16)
*   `ECHO` -> Pi GPIO 24 (Pin 18)  *(**Warning**: Put a 1k resistor from ECHO to GPIO 24, and a 2k resistor from GPIO 24 to GND to step the 5V signal down to 3.3V.)*

## 3. Flashing the ESP32-CAM
1.  Open `esp32_cam/esp32_cam.ino` in the Arduino IDE.
2.  Install the **ESP32 Board Manager** via Arduino IDE settings.
3.  Select **AI Thinker ESP32-CAM** under Tools -> Board.
4.  Change the `ssid` and `password` variables in the code to your Wi-Fi credentials (e.g., your mobile hotspot or home network).
5.  Compile and upload using an FTDI Programmer.
6.  Once running, open the Serial Monitor (115200 baud) to find the ESP32's assigned IP Address.
7.  Update `pi_edge/main.py` line `26` with this IP Address.

## 4. Raspberry Pi Deployment Steps

Perform these steps on your Windows PC to push this code, then pull it on your Raspberry Pi.

### Step A: Push from Windows to GitHub
1.  Open Command Prompt or PowerShell in this folder (`c:\Users\Osama\OneDrive\Desktop\pothole`)
2.  Initialize the repository and push to your GitHub:
    ```bash
    git init
    git add .
    git commit -m "Initial SmartRoad 3D release"
    git branch -M main
    git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
    git push -u origin main
    ```

### Step B: Pull and Run on Raspberry Pi Linux
1.  SSH into your Raspberry Pi or open the terminal locally.
2.  Clone the repository:
    ```bash
    git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
    cd YOUR_REPOSITORY/pi_edge
    ```
3.  Install dependencies:
    ```bash
    sudo apt update
    sudo apt install python3-pip python3-opencv
    pip3 install pyserial RPi.GPIO requests numpy matplotlib
    ```
4.  Run the main system loop:
    ```bash
    python3 main.py
    ```

## 5. System Features
*   **Dual Depth Fusion:** Continuously queries the TF-Luna LiDAR. If invalid data or a disconnection occurs, seamlessly switches to the HC-SR04 logic.
*   **3D Mesh Modeling:** When an anomaly is detected (>5cm relative depth), it captures a rolling depth buffer and artificially sweeps it laterally to create an `.obj` 3D mesh map and a `.png` topology plot.
*   **Remote Vision:** Triggers the ESP32-CAM over HTTP to snapshot the pothole synchronously. All data is saved to the `pi_edge/scans_3d/` folder on your Pi.
