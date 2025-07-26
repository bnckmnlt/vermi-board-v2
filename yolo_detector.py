import cv2
from tracker import Tracker
from ultralytics import YOLO
from constants import RAND_COLORS
from dataclasses import dataclass


class YOLODetector:
    def __init__(
        self, 
        model_path: str,
        resolution: tuple[int, int] = (640, 640),
        imgsz: int = 640,
        confidence: float = 0.2,
        tracker: Tracker = Tracker()
    ):
        self.model = YOLO(model_path, task="detect")
        self.resolution = resolution
        self.imgz = imgsz
        self.confidence = confidence
        self.tracker = tracker
        
    def detect(self, frame):
        results = self.model(frame, conf=self.confidence, verbose=False, show=False)
        result = results[0]

        detections, metadata = self.make_detections(result)
        
        return detections, metadata
        
    def make_detections(self, result):
        boxes = result.boxes
        detections = []
        metadata = []
        
        for box in boxes.data.tolist():
            x1, y1, x2, y2, conf, class_id = box
            x1, y1, x2, y2, class_id = map(int, (x1, y1, x2, y2, class_id))
            cls = self.model.names[class_id]

            detections.append([x1, y1, x2, y2, conf])
            metadata.append(((x1, y1, x2, y2), conf, cls))
        
        return detections, metadata
    
    def draw_detections(self, frame, detections, metadata):
        self.tracker.update(frame, detections)
        annotated_detections = []

        for track in self.tracker.tracks:
            x1, y1, x2, y2 = map(int, track.bbox)
            track_id = track.track_id
            color = RAND_COLORS[track_id % len(RAND_COLORS)]
            
            label = 'unknown'
            for _, conf, cls in metadata:
                label = f'{cls}: {conf:.2f}%'
                annotated_detections.append(
                    Metadata(
                        track_id=track_id,
                        bbox=(x1, y1, x2, y2),
                        conf=conf,
                        cls=cls
                    )
                )
                break
                
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - text_h - 4), (x1 + text_w, y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return frame, annotated_detections
    
    def classify_object_region(self, metadata, frame_width):
        region_width = frame_width // 3
        region_classes = {
            'entry': [],
            'middle': [],
            'exit': [],
        }
        
        for obj in metadata:
            x1, _, x2, _ = map(int, obj.bbox)
            center_x = (x1 + x2) / 2
            
            if center_x < region_width:
                region = "exit"
            elif center_x < region_width * 2:
                region = "middle"
            else:
                region = "entry"
            
            region_classes[region].append(obj)
            
        return region_classes
    
    def exit_clear(self, regions):
        return len(regions["exit"]) == 0
    

@dataclass
class Metadata:
    track_id: int
    bbox: tuple[int, int, int, int]
    conf: float
    cls: str