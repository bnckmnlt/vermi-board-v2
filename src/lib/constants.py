import random


MEGA_SERIAL_PORT = "/dev/ttyUSB0"
UNO_SERIAL_PORT = "/dev/ttyACM0"
MEGA_SERIAL_BAUD = 115200
UNO_SERIAL_BAUD = 115200
SERIAL_CONN = None

DEFAULT_LAYERS = {
    "bedding": {},
    "compost": {},
    "fluids": {}
}

RELAY_CONFIG = {
    0: [0, 1, 2, 3],
    1: [0, 1, 2, 3]
}

CONTROL_TOPICS = [
    "control/aeration",
    "control/sifter",
    "control/fan",
    "control/pump",
    "control/relay",
    "control/conveyor",
    "control/vermijuice",
    "control/rake",
    "control/monitoring/thermal",
    "control/monitoring/camera",
    "system/current_cycle",
    "system/feeding/id",
    "system/status",
    "system/settings",
]

# CAMERA SERVICE CONFIG()
CAMERA_WIDTH = 768
CAMERA_HEIGHT = 1024
RESOLUTION = (768, 1024)
OUTPUT_DIR = "./public/detections"
MODEL_PATH = '/home/raspi/projects/practice_design/yolo11s_ncnn_model'

RAND_COLORS = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for j in range(10)]

VALID_CLASSES = ["fruit", "vegetable", "grains"]
INVALID_CLASSES = ["citrus", "meat", "foreign"]