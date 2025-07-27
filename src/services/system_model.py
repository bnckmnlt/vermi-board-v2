from enum import Enum
import adafruit_mlx90640

class Status(Enum):
    ACTIVE = "active"
    FEEDING = "feeding"
    IDLE = "idle"

class SystemSettings:
    def __init__(
        self,
        id: int = 0,
        status: Status = Status.IDLE,
        reading_interval: int = 30,
        refresh_rate: any = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
    ):
        self.id = id
        self.status = status
        self.reading_interval = reading_interval
        self.worm_refresh_rate = refresh_rate

    def update(self, **kwargs):
        self._apply_updates(kwargs)

    def update_from_dict(self, data: dict):
        self._apply_updates(data)

    def _apply_updates(self, updates: dict):
        for key, value in updates.items():
            if key == 'status':
                try:
                    self.status = Status(value) if isinstance(value, str) else value
                except ValueError:
                    continue
            elif key == 'id':
                self.id = int(value)
            elif key == 'reading_interval':
                self.reading_interval = int(value)
            elif key == 'refresh_rate':
                if value == 4:
                    self.worm_refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
                elif value == 8:
                    self.worm_refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
                elif value == 16:
                    self.worm_refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_16_HZ 
                else:
                    self.worm_refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
