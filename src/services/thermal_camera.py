import logging
from threading import Thread
from time import sleep
import cv2
import numpy as np
import board
import busio
import adafruit_mlx90640
from flask import Flask, Response
from werkzeug.serving import make_server


class ThermalCameraProcessor:
    def __init__(self, refresh_rate=adafruit_mlx90640.RefreshRate.REFRESH_2_HZ):
        i2c = busio.I2C(board.SCL, board.SDA)
        self.mlx = adafruit_mlx90640.MLX90640(i2c)
        self.mlx.refresh_rate = refresh_rate
        self.frame = np.zeros((24 * 32,), dtype=float)
        self.app = Flask(__name__)
        self._setup_routes()
        self.server = None
        self.should_stream = False
        self.running = False

    def set_refresh_rate(self, rate):
        self.mlx.refresh_rate = rate

    def _get_thermal_array(self):
        self.mlx.getFrame(self.frame)
        return self.frame.reshape((24, 32))

    def _process_image(self, data_array):
        norm = cv2.normalize(data_array, None, 0, 255, cv2.NORM_MINMAX)
        norm = np.uint8(norm)
        color_image = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)
        resized = cv2.resize(color_image, (320, 320), interpolation=cv2.INTER_CUBIC)

        overlay = resized.copy()
        zone_size = 320 // 2

        for i in range(2):
            for j in range(2):
                x, y = j * zone_size, i * zone_size
                cv2.rectangle(overlay, (x, y), (x + zone_size, y + zone_size), (255, 255, 255), 1)
                label = chr(65 + i * 2 + j)
                cv2.putText(overlay, label, (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        region = data_array[4:20, 8:24]
        hotspot = self._get_hotspot_centroid(region)
        if hotspot:
            y, x = hotspot
            x_scaled = int((x + 8) * 10)
            y_scaled = int((y + 4) * 20)
            cv2.circle(overlay, (x_scaled, y_scaled), 6, (0, 255, 255), -1)

        return overlay

    def _infer_activity(self, region):
        avg, max_ = np.mean(region), np.max(region)
        spread = max_ - avg
        if spread < 1.5:
            return 'low', spread
        elif spread < 4.0:
            return 'moderate', spread
        return 'high', spread

    def _get_hotspot_centroid(self, region, threshold_delta=1.5):
        threshold = np.mean(region) + threshold_delta
        coords = np.argwhere(region >= threshold)
        if coords.size > 0:
            return np.mean(coords, axis=0).tolist()
        return None

    def _extract_zones(self, region):
        zones = {
            "A": region[0:8, 0:8],
            "B": region[0:8, 8:16],
            "C": region[8:16, 0:8],
            "D": region[8:16, 8:16],
        }
        zone_data = {}
        for name, z in zones.items():
            avg, max_ = np.mean(z), np.max(z)
            level, spread = self._infer_activity(z)
            zone_data[name] = {
                "avg_temp": round(avg, 2),
                "max_temp": round(max_, 2),
                "spread": round(spread, 2),
                "activity_level": level
            }
        return zone_data

    def get_metrics(self):
        region = self._get_thermal_array()[4:20, 8:24]
        avg_temp = float(f"{np.mean(region):.2f}")
        max_temp = float(f"{np.max(region):.2f}")
        min_temp = float(f"{np.min(region):.2f}")
        activity_level, spread = self._infer_activity(region)
        spread = float(f"{spread:.2f}")
        hotspot = self._get_hotspot_centroid(region)
        zones = self._extract_zones(region)

        return {
            "avg_temp": avg_temp,
            "max_temp": max_temp,
            "min_temp": min_temp,
            "thermal_spread": spread,
            "activity_level": activity_level,
            "hotspot": hotspot,
            "zones": zones
        }

    # Flask server methods
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return Response(self._generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

    def _generate_mjpeg(self):
        while self.should_stream:
            try:
                array = self._get_thermal_array()
                frame = self._process_image(array)
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                sleep(0.05)
            except GeneratorExit:
                break
            except Exception as e:
                logging.error(f"[Thermal] MJPEG error: {e}")
                break

    def start_server(self, host='0.0.0.0', port=5000):
        if not self.running:
            self.should_stream = True
            self.server = make_server(host, port, self.app)
            self.server_thread = Thread(target=self.server.serve_forever, name="thermal_camera_server", daemon=True)
            self.server_thread.start()
            self.running = True
            logging.info("[Thermal] Server started")

    def run_forever(self):
        if self.server:
            self.server_thread()

    def stop_server(self):
        if self.server and self.running:
            try:
                logging.info("[Thermal] Shutting down...")
                self.should_stream = False
                self.server.shutdown()
                self.server_thread.join(timeout=5)
            except Exception as e:
                logging.info(f"[Thermal] Shutdown error: {e}")
            finally:
                self.server = None
                self.server_thread = None
                self.running = False
                logging.info("[Thermal] Server stopped")
