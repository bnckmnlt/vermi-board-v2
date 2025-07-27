from dataclasses import dataclass


@dataclass
class UploadItem:
    track_id: int
    cls: str
    conf: float
    path: str
    
@dataclass
class Track:
    track_id: int = None
    bbox: tuple[int, int, int, int] = None
        
@dataclass
class Metadata:
    track_id: int
    bbox: tuple[int, int, int, int]
    conf: float
    cls: str