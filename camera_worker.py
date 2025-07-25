import os
import time
import threading
import json
import logging
import sys
import requests
import cv2

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from ultralytics import YOLO
from picamera2 import Picamera2
from libcamera import controls
from uvicorn import Config, Server

from uno_serial import UnoSerialProcessor
from system_model import Status, SystemSettings

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

class CameraProcessor:
    def __init__(
        self,
        model_path: str,
        resolution=(320, 320),
        conf=0.5,
        save_dir="./detections",
        invalid_classes=None,
        host="0.0.0.0",
        port=8080,
        bucket_client=None,
        bucket_name=None,
        uno: UnoSerialProcessor = None,
        settings: SystemSettings = None,
    ):        
        # System Detail Vars
        self.id = 1
        self.uno_serial = uno
        self.settings = settings

        # Model & storage
        self.model = YOLO(model_path, task="detect")
        self.confidence = conf
        self.save_dir = save_dir
        self.invalid_classes = invalid_classes or set()
        ensure_dir(self.save_dir)

        # Camera setup
        self.picam2 = Picamera2()
        self._configure_camera(resolution)

        # State
        self.running = False
        self.current_frame = None
        self.prev_center = set()
        self.entry_info = {}

        # FastAPI app
        self.app = FastAPI()
        self.host = host
        self.port = port
        self._register_routes()

        # Server thread handle
        self._server_thread = None

    def update_id(self, new_id: int):
        if isinstance(new_id, int) and new_id > 0:
            self.id = new_id
            logging.info(f"Feeding ID updated to {self.id}")
        else:
            logging.warning(f"Ignored invalid feeding ID value: {new_id}")

    def _configure_camera(self, resolution):
        self.picam2.preview_configuration.main.size = resolution
        self.picam2.preview_configuration.main.format = "RGB888"
        self.picam2.preview_configuration.align()

        self.picam2.preview_configuration.controls = {
            "HdrMode": controls.HdrModeEnum.SingleExposure,
            "AfMode": controls.AfModeEnum.Continuous,
            "AeEnable": True,
            "AwbEnable": True,
            "Sharpness": 1.8,
            "Contrast": 1.4,
            "Brightness": 0.2,
            "Saturation": 1.3,
            "NoiseReductionMode": 2,
        }

        self.picam2.configure("preview")

    def _register_routes(self):
        @self.app.get("/video_feed")
        def video_feed():
            return StreamingResponse(
                self._frame_generator(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )

    def _frame_generator(self):
        while self.running:
            if self.current_frame is not None:
                _, buf = cv2.imencode('.jpg', self.current_frame)
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n'
            time.sleep(1 / 30)

    def _process_frame(self, frame):
        self.current_frame = frame.copy()

        if self.settings.status != Status.FEEDING:
            return

        results = self.model(frame, conf=self.confidence, imgsz=320, show=False, verbose=False)
        self.current_frame = results[0].plot()

        h = frame.shape[0]
        y_min, y_max = h // 3, (h // 3) * 2

        current = set()
        detections = []

        for *coords, conf, cls in results[0].boxes.data.tolist():
            cy = (coords[1] + coords[3]) / 2
            name = self.model.names[int(cls)]
            detections.append((name, coords, conf))
            if y_min < cy <= y_max:
                current.add(name)

        if not self.prev_center and current:
            self.entry_info.clear()
            self._save_and_enqueue_uploads(frame, detections)

        elif self.prev_center and not current:
            self._handle_exit(self.prev_center, self.entry_info)

        self.prev_center = current

    def _save_and_enqueue_uploads(self, frame, detections):
        ts = int(time.time() * 1000)
        for cls, coords, conf in detections:
            x1, y1, x2, y2 = map(int, coords[:4])
            crop = frame[y1: y2, x1: x2]
            fname = f"{cls}_{ts}.jpg"
            path = os.path.join(self.save_dir, fname)
            cv2.imwrite(path, crop)
            self.entry_info.setdefault(cls, []).append((conf, path))

    def _handle_exit(self, classes, entry_info):
        action = "EJECT" if (classes & self.invalid_classes) else "PASS"

        if action == "EJECT":
            self.uno_serial.send_data("<Conveyor:Eject>")
            
        logging.info(f"Action: {action} for {classes}")

        for cls, records in entry_info.items():
            for conf, path in records:
                payload = {
                    "foodWasteScheduleId": self.id,
                    "materialStatus": "valid" if cls not in self.invalid_classes else "invalid",
                    "confidence": conf,
                    "classname": cls
                }
                logging.info("Enqueue upload: %s", payload)
                threading.Thread(
                    target=self.send_request,
                    name="upload_to_server",
                    args=(path, payload),
                    daemon=True
                ).start()

    def send_request(self, filepath: str, payload: dict):
        try:
            url = f"{os.getenv('SERVER_URL')}/food-waste"
            with open(filepath, "rb") as f:
                files = {"file": (os.path.basename(filepath), f, "image/png")}
                data = {k: str(v) for k, v in payload.items()}
                r = requests.post(url, files=files, data=data)
                logging.info(f"Upload response: {r.status_code} - {r.text}")
        except Exception as e:
            logging.error("Upload error: %s", e)

    def start_server(self):
        if getattr(self, "_server_thread", None) and self._server_thread.is_alive():
            return

        def _serve():
            config = Config(app=self.app, host=self.host, port=self.port, log_level="info", access_log=False)
            self._uvicorn_server = Server(config)
            self._uvicorn_server.run()

        self._server_thread = threading.Thread(target=_serve, name="camera_stream_fastapi", daemon=True)
        self._server_thread.start()
        logging.info("FastAPI server thread started.")

    def start_stream(self):
        if self.running:
            return
        self.running = True
        self.picam2.start()
        logging.info("Camera stream started.")
        self.start_server()

        try:
            while self.running:
                frame = self.picam2.capture_array()
                self._process_frame(frame)
                time.sleep(0.05)
        except Exception as e:
            logging.error("Stream error: %s", e)
        finally:
            self.stop()

    def stop(self):
        if not self.running:
            return

        self.running = False
        logging.info("Stopping camera stream...")

        try:
            if hasattr(self, 'picam2') and self.picam2 is not None:
                self.picam2.stop()
                logging.info("Camera stopped successfully")
        except Exception as e:
            logging.error(f"Failed to stop camera: {e}")

        try:
            if hasattr(self, '_uvicorn_server'):
                self._uvicorn_server.should_exit = True

            if hasattr(self, '_server_thread') and self._server_thread.is_alive():
                logging.info("Waiting for server thread to terminate...")
                self._server_thread.join(timeout=5)
                if self._server_thread.is_alive():
                    logging.warning("Server thread did not terminate within timeout.")
                else:
                    logging.info("FastAPI server thread stopped.")
            else:
                logging.info("No active server thread.")
        except Exception as e:
            logging.error(f"Failed to stop server thread: {e}")

        try:
            cv2.destroyAllWindows()
            logging.info("OpenCV windows destroyed")
        except Exception as e:
            logging.error(f"Failed to destroy OpenCV windows: {e}")
