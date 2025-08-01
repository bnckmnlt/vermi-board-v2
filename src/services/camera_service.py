from queue import Queue, Empty
import logging
import os
from threading import Thread
import requests
import cv2
from gpiozero import InputDevice
from time import sleep
from libcamera import controls
from picamera2 import Picamera2
from dataclasses import dataclass, field

from src.lib.constants import MODEL_PATH, RESOLUTION, OUTPUT_DIR, INVALID_CLASSES, VALID_CLASSES
from src.lib.entities import UploadItem
from src.lib.utils import ensure_dir, expand_crop_box, generate_filename, create_payload
from src.serials.uno_serial import UnoSerialProcessor
from src.services.system_model import SystemSettings, Status
from src.services.fast_api_service import FastAPIApp
from src.services.yolo_detector_service import Metadata, YOLODetectorService
from src.services.tracker import Tracker

      
@dataclass
class CameraService:
    uno_serial: UnoSerialProcessor = field(repr=False)
    settings: SystemSettings = field(repr=False)

    system_id: int = 1
    model_path: str = MODEL_PATH
    resolution: tuple[int, int] = RESOLUTION
    conf: float = 0.8
    imgsz: int = 640
    output_dir: str = OUTPUT_DIR
    invalid_classes: list[str] = field(default_factory=lambda: INVALID_CLASSES)
    valid_classes: list[str] = field(default_factory=lambda: VALID_CLASSES)
    
    picam: Picamera2 = field(init=False)
    traker: Tracker = field(init=False)
    model: YOLODetectorService = field(init=False)
    app: FastAPIApp = field(init=False)
    frame: any = field(init=False)
    ir_sensor: InputDevice = field(init=False)
    
    is_running: bool = False
    diverter_locked: bool = False
    
    uploaded_ids: set = field(default_factory=list)
    entry_info: dict = field(default_factory=dict)
    upload_queue: Queue = field(default_factory=Queue)
    upload_thread: Thread = field(init=False)
    is_uploading: bool = field(default=False)
    
    def __post_init__(self):
        ensure_dir(self.output_dir)
        self.uploaded_ids = set()
        
        self.picam = Picamera2()
        self._configure_camera()

        self.tracker = Tracker()

        self.yolo = YOLODetectorService(
            self.model_path,
            resolution=self.resolution,
            imgsz=self.imgsz,
            confidence=self.conf,
            tracker=self.tracker
        )
        
        self.ir_sensor = InputDevice(17)
        
        self.upload_thread = Thread(
            target=self._process_upload,
            name="upload_worker",
            daemon=True
        )
        self.upload_thread.start()
        
    def update_id(self, new_id: int):
        if isinstance(new_id, int) and new_id > 0:
            self.system_id = new_id
            logging.info(f"Feeding ID updated to {self.system_id}")
        else:
            logging.warning(f"Ignored invalid feeding ID value: {new_id}")
        
    def _configure_camera(self):
        self.picam.preview_configuration.main.size = self.resolution
        self.picam.preview_configuration.main.format = "RGB888"
        self.picam.preview_configuration.align()
        self.picam.preview_configuration.controls = {
            "HdrMode": controls.HdrModeEnum.SingleExposure,
            "AfMode": controls.AfModeEnum.Continuous,
        }
        self.picam.configure("preview")
    
    def _begin_detection(self, frame):
        detections, metadata = self.yolo.detect(frame)
        annotated_frame, annotations = self.yolo.draw_detections(frame, detections, metadata)
        self.frame = annotated_frame if self.settings.status == Status.FEEDING else frame 
        self.app.frame = self.frame

        regions = self.yolo.classify_object_region(annotations, frame.shape[1])
        
        for region, objects in regions.items():
            region_has_invalid = any(obj.cls in INVALID_CLASSES for obj in objects)
            
            if region == 'entry':
                pass

            if region == 'middle':
                self._save_image(annotated_frame, objects, region)
            
            elif region == "exit":
                if self.ir_sensor.is_active:
                    if region_has_invalid and not self.diverter_locked:
                        self.uno_serial.send_data("<Conveyor:Eject:0>")
                        self.diverter_locked = True

                elif self.diverter_locked and not region_has_invalid and self.yolo.exit_clear(regions):
                    self.uno_serial.send_data("<Conveyor:Eject:90>")
                    
                self.diverter_locked = False
    
    def _save_image(self, frame, annotations: list[Metadata], region):
        for metadata in annotations:
            if region == "middle" and metadata.track_id not in self.uploaded_ids:
                h, w = frame.shape[:2]
                x1, y1, x2, y2 = map(int, metadata.bbox)
                x1, y1, x2, y2 = expand_crop_box(x1, y1, x2, y2, w, h, margin=0.4)
                cropped_frame = frame[y1: y2, x1: x2]
                filename = generate_filename(metadata.track_id, metadata.cls, metadata.conf)

                path = os.path.join(self.output_dir, filename)
                cv2.imwrite(path, cropped_frame)

                self.entry_info.setdefault(metadata.cls, []).append((metadata.conf, path))
                self.upload_queue.put(UploadItem(metadata.track_id, metadata.cls, metadata.conf, path))
                self.uploaded_ids.add(metadata.track_id)
                
    def _process_upload(self):
        self.is_uploading = True
        
        while self.is_uploading:
            try:
                item = self.upload_queue.get(timeout=1)
                payload = create_payload(self.system_id, item.cls, item.conf)

                self._send_request(item.path, payload)
            except Empty:
                continue
            
    def _stop_uploading(self):
        self.is_uploading = False

        if self.upload_thread.is_alive():
            self.upload_thread.join()

    def _send_request(self, filepath: str, payload: dict):
        try:
            url = f"{os.getenv('SERVER_URL')}/food-waste"
            with open(filepath, "rb") as f:
                files = {"file": (os.path.basename(filepath), f, "image/png")}
                data = {k: str(v) for k, v in payload.items()}
                r = requests.post(url, files=files, data=data)
                logging.info(f"Upload response: {r.status_code} - {r.text}")
        except Exception as e:
            logging.error("Upload error: %s", e)
    
    def start_stream(self):
        if self.is_running:
            return
    
        self.is_running = True
        self.picam.start()
        
        self.app = FastAPIApp(
            is_running=self.is_running,
        )
        self.app.start_server()
        logging.info("Camera stream started..")

        try:
            while self.is_running:
                frame = self.picam.capture_array()
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                
                if self.settings.status == Status.FEEDING:
                    self._begin_detection(frame)
                else:
                    self.frame = frame
                    self.app.frame = frame
                
                sleep(0.05)
        except Exception as e:
            logging.error("Stream error: %s", e)
        finally:
            self.stop_stream()
            self._stop_uploading()
        
    def stop_stream(self):
        if not self.is_running:
            return
                
        self.is_running = False
        logging.info("Stopping camera stream...")
        
        try:
            self.app.stop_server()
            self.picam.stop()
            cv2.destroyAllWindows()
            logging.info("Camera stopped successfully")
        except Exception as e:
            logging.error(f"Failed to stop camera: {e}")