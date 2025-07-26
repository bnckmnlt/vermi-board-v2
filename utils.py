import os
import logging
import unicodedata
from datetime import datetime
from constants import INVALID_CLASSES
from colorama import Fore, Style, init

def clean_unicode(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

def to_number(value, default=0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def evaluate_health(layers):
    total_checks = 7
    failed_checks = 0
    issues = []

    compost_npk = layers.get("compost", {}).get("npk", {})
    if all(compost_npk.get(nutrient, 0) == 0 for nutrient in ["nitrogen", "phosphorus", "potassium"]):
        issues.append("NPK values are all zero")
        failed_checks += 1

    compost_weight = layers.get("compost", {}).get("compost_weight", {}).get("value", 0)
    if compost_weight <= 0:
        issues.append("Compost processed is empty")
        failed_checks += 1

    fluid = layers.get("fluid", {})

    if fluid.get("reservoir_weight", {}).get("value", 0) <= 0:
        issues.append("Reservoir is empty")
        failed_checks += 1
    if fluid.get("juice_weight", {}).get("value", 0) <= 0:
        issues.append("No juice collected")
        failed_checks += 1

    bedding = layers.get("bedding", {})
    temp = bedding.get("temperature", {}).get("value", 0)
    humidity = bedding.get("humidity", {}).get("value", 0)
    soil_moisture = bedding.get("soil_moisture", {}).get("value", 0)

    if temp < 15 or temp > 40:
        issues.append(f"Temperature out of range: {temp}°C")
        failed_checks += 1
    if humidity < 30 or humidity > 70:
        issues.append(f"Humidity suboptimal: {humidity}%")
        failed_checks += 1
    if soil_moisture < 10:
        issues.append(f"Soil moisture too low: {soil_moisture}%")
        failed_checks += 1

    health_percent = round((1 - min(failed_checks, total_checks) / total_checks) * 100, 2)

    if health_percent >= 80:
        status = "Healthy"
    elif health_percent >= 50:
        status = "Moderate"
    elif health_percent >= 30:
        status = "Warning"
    else:
        status = "Critical"

    return {
        "status": status,
        "issues": issues,
        "health_percent": health_percent
    }

init(autoreset=True)

class ColorFormatter(logging.Formatter):
    COLOR_MAP = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT
    }

    def format(self, record):
        color = self.COLOR_MAP.get(record.levelno, "")
        record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def generate_filename(track_id: int, classname: str, confidence: float) -> str:
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    return f"{classname}_{track_id}_{confidence:.2f}_{timestamp}.jpg"

def expand_crop_box(x1, y1, x2, y2, frame_width, frame_height, margin=0.2):
    box_width = x2 - x1
    box_height = y2 - y1

    expand_w = int(box_width * margin / 2)
    expand_h = int(box_height * margin / 2)

    new_x1 = max(0, x1 - expand_w)
    new_y1 = max(0, y1 - expand_h)
    new_x2 = min(frame_width, x2 + expand_w)
    new_y2 = min(frame_height, y2 + expand_h)

    return new_x1, new_y1, new_x2, new_y2

def create_payload(id: int, cls: str, conf: float):
    return {
        "foodWasteScheduleId": 3,
        "materialStatus": "valid" if cls not in INVALID_CLASSES else "invalid",
        "confidence": conf,
        "classname": cls
    }