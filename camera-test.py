from queue import Empty, Queue
import cv2
from gpiozero import InputDevice
from libcamera import controls
from picamera2 import Picamera2, Preview
from src.services.yolo_detector_service import YOLODetectorService
from src.services.tracker import Tracker
from src.lib.constants import CAMERA_WIDTH, CAMERA_HEIGHT, RAND_COLORS

# Camera Configuration
picam2 = Picamera2()
picam2.preview_configuration.main.size = (CAMERA_WIDTH, CAMERA_HEIGHT)
picam2.preview_configuration.main.format = "RGB888"
picam2.preview_configuration.align()
picam2.preview_configuration.controls = {
    "HdrMode": controls.HdrModeEnum.SingleExposure,
    "AfMode": controls.AfModeEnum.Continuous,
}
picam2.configure("preview")
picam2.start()

# deepSORT
tracker = Tracker()

# YOLO
yolo = YOLODetectorService("../practice_design/yolo11s_ncnn_model", resolution=(CAMERA_WIDTH, CAMERA_HEIGHT), imgsz=640, confidence=0.8, tracker=tracker)

valid_classes = ["mouse"]
invalid_classes = ["person", "cell phone"]
uploaded_ids = set()

# IR Sensor
ir_sensor = InputDevice(17)
diverter_locked = False
upload_queue: Queue = Queue()

while True:
    frame = picam2.capture_array()
    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    
    detections, metadata = yolo.detect(frame)
    
    frame, annotated = yolo.draw_detections(frame, detections, metadata)

    regions = yolo.classify_object_region(annotated, CAMERA_WIDTH)

    
    for region, objects in regions.items():
        region_has_valid = any(obj.cls in valid_classes for obj in objects)
        region_has_invalid = any(obj.cls in invalid_classes for obj in objects)
        
        if region == 'entry':
            for obj in objects:
                if obj.track_id not in uploaded_ids:
                    print("Saving image")
                    uploaded_ids.add(obj.track_id)
                    upload_queue.put(obj.track_id)
                    
        if region == 'middle':
            try:
                item = upload_queue.get(timeout=1)
                print(f"Uploading image id: {item}")
            except Empty:
                continue
                # print("Empty")
        
        elif region == 'exit':
            if ir_sensor.is_active == False:
                if region_has_invalid and not diverter_locked:
                    print("Send servo to BLOCK")
                    diverter_locked = True

            elif diverter_locked and not region_has_invalid and yolo.exit_clear(regions):
                print("Send servo to UNBLOCK")
            diverter_locked = False
    
    
    cv2.imshow("Camera Preview", frame)
    
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
    
cv2.destroyAllWindows()
picam2.stop()
    
# x = 0, y = 0
#  x = exit_point, y = h 