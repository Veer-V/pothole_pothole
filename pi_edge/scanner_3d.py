import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import datetime
import os

class Scanner3D:
    def __init__(self, window_size=50, width_cm=40):
        self.window_size = window_size
        self.width_cm = width_cm
        self.depth_buffer = []  # rolling buffer of the last N depth readings
        self.output_dir = "scans_3d"
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def add_reading(self, depth_cm):
        """ Adds a single point reading to the buffer """
        # We cap the depth buffer length to window_size
        self.depth_buffer.append(depth_cm)
        if len(self.depth_buffer) > self.window_size:
            self.depth_buffer.pop(0)

    def generate_3d_model(self, event_type="anomaly"):
        """ Generates a 3D surface mesh from the 1D rolling buffer of depths and saves it """
        if len(self.depth_buffer) < 10:
            print("Not enough data to gen 3D model.")
            return None
        
        # We simulate a 2D surface by widening the 1D depth profile across a lateral width
        # The sensor scans one line, so we extrapolate that line into a "strip" of road
        y_points = np.linspace(0, len(self.depth_buffer) * 2, len(self.depth_buffer)) # Distance forward (cm)
        x_points = np.linspace(-self.width_cm/2, self.width_cm/2, 20)                 # Lateral width (cm)
        
        X, Y = np.meshgrid(x_points, y_points)
        
        # Base Road is at Z=0. 
        # depth_cm is relative to the road; Positive = Pothole (goes down), Negative = Speed bump (goes up)
        # So Z elevation = -depth_cm
        Z = np.zeros_like(X)
        for i in range(len(self.depth_buffer)):
            # Taper the edges so it looks more like a natural bump/hole
            Z[i, :] = -self.depth_buffer[i] * np.cos(np.linspace(-np.pi/2, np.pi/2, 20))
            
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection='3d')
        surf = ax.plot_surface(X, Y, Z, cmap='terrain', edgecolor='none')
        
        road_type = "Speed Bump" if (max(self.depth_buffer) * -1) > 0 else "Pothole"
        ax.set_title(f'3D Profile: {road_type} Detected')
        ax.set_xlabel('Width (cm)')
        ax.set_ylabel('Length Travelled (cm)')
        ax.set_zlabel('Elevation (cm)')
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.output_dir}/scan_{event_type}_{timestamp}.png"
        obj_filename = f"{self.output_dir}/scan_{event_type}_{timestamp}.obj"
        
        plt.savefig(filename)
        plt.close()
        
        # Also generate an OBJ file
        self._export_obj(X, Y, Z, obj_filename)
        
        print(f"[{timestamp}] 3D Model Saved: {filename} and {obj_filename}")
        return filename

    def _export_obj(self, X, Y, Z, filename):
        """ Basic Wavefront .obj exporter """
        rows, cols = Z.shape
        with open(filename, 'w') as f:
            f.write("# 3D Road Profile\n")
            # Write vertices
            for r in range(rows):
                for c in range(cols):
                    f.write(f"v {X[r,c]:.2f} {Z[r,c]:.2f} {Y[r,c]:.2f}\n")
            
            # Write faces (1-indexed)
            for r in range(rows - 1):
                for c in range(cols - 1):
                    v1 = r * cols + c + 1
                    v2 = r * cols + (c + 1) + 1
                    v3 = (r + 1) * cols + c + 1
                    v4 = (r + 1) * cols + (c + 1) + 1
                    # Two triangles per quad
                    f.write(f"f {v1} {v2} {v4}\n")
                    f.write(f"f {v1} {v4} {v3}\n")
