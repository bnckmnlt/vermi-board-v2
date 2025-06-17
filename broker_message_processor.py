import json
import logging
import threading

from constants import RELAY_CONFIG
from system_model import Status, SystemSettings
from camera_worker import CameraProcessor
from thermal_camera import ThermalCameraProcessor
from mega_serial import MegaSerialProcessor
from uno_serial import UnoSerialProcessor

class BrokerMessageProcessor:
    def __init__(self, settings: SystemSettings, thermal_camera: ThermalCameraProcessor, camera_inference: CameraProcessor, mega: MegaSerialProcessor, uno: UnoSerialProcessor,):
        self.mega = mega
        self.uno = uno

        self.settings = settings

        self.camera_inference = camera_inference
        self.camera_inference_started = False
        self.camera_thread = None

        self.thermal_camera = thermal_camera
        self.thermal_camera_started = False
        self.thermal_thread = None
        
        self.topics = {
                "system/status": self.handle_system_status,
                "system/current_cycle": self.handle_system_cycle,
                "system/feeding/id": self.handle_feeding_id,
                "system/settings": self.handle_system_settings,
                "control/fan": self.handle_fan,
                "control/aeration": self.handle_aeration,
                "control/pump": self.handle_pump,
                "control/sifter": self.handle_sifter,
                "control/relay": self.handle_relay,
                "control/conveyor": self.handle_conveyor,
                "control/vermijuice": self.handle_vermijuice,
                "control/rake": self.handle_rake,
                "control/monitoring/thermal": self.handle_thermal_monitoring,
                "control/monitoring/camera": self.handle_camera_inference,
            }
        
        for board, relays in RELAY_CONFIG.items():
            for relay in relays:
                topic = f"feedback/relay/{board}/{relay}"
                self.topics[topic] = self.handle_relay_feedback

    def handle_fan(self, payload): self.mega.send_data(f"<Fan:{payload}>")
    def handle_aeration(self, payload): self.mega.send_data(f"<Aeration:{payload}>")
    def handle_pump(self, payload): self.mega.send_data(f"<Pump:{payload}>")
    def handle_sifter(self, payload): self.mega.send_data(f"<Sifter:{payload}>")
    def handle_relay(self, payload): self.mega.send_data(f"<Relay:{payload}>")
    def handle_conveyor(self, payload): self.uno.send_data(f"<Conveyor:{payload}>")
    def handle_vermijuice(self, payload): self.uno.send_data(f"<Vermijuice:{payload}>")
    def handle_rake(self, payload): self.uno.send_data(f"<Rake:{payload}>")
                
    def on_message(self, client, userdata, message):
        payload = message.payload.decode("utf-8")
        handler = self.topics.get(message.topic)
        if handler:
            handler(payload)
        else:
            logging.error(f"Received message on unknown topic: {message.topic}")

    def handle_feeding_id(self, payload):
        try:
            self.camera_inference.update_id(int(payload))
            logging.info(f"Feeding ID updated to {self.camera_inference.id}")
        except ValueError:
            logging.warning(f"Ignored invalid feeding ID value: {payload}")

            
    def handle_relay_feedback(self, topic, payload):
        board, relay = map(int, topic.split("/")[-2:])
        state = int(payload)
        logging.info(f"Relay {relay} on board {board} updated to {state}")
        
    def handle_system_cycle(self, payload):
        try:
            self.settings.update(id=int(payload))
        except ValueError:
            logging.warning(f"Ignored invalid id value: {payload}")

    def handle_system_status(self, payload):
        try:
            self.settings.update(status=Status(payload))
        except ValueError:
            logging.warning(f"Ignored invalid status value: {payload}")

    def handle_thermal_monitoring(self, payload):
        enable = payload.lower() in ("true", "1", "on", "active")

        if enable and not self.thermal_camera_started:
            logging.info("Starting thermal camera monitoring…")
            self.thermal_camera.start_server()
            self.thermal_camera_started = True

        elif not enable:
            logging.info("Stopping thermal camera monitoring…")
            self.thermal_camera.stop_server()
            self.thermal_camera_started = False

    def handle_camera_inference(self, payload):
        enable = payload.lower() in ("true", "1", "on", "active")

        if enable and not self.camera_inference_started:
            self.camera_thread = threading.Thread(target=self.camera_inference.start_stream, name="broker_start_stream", daemon=True).start()
            self.camera_inference_started = True

        elif not enable:
            self.camera_inference.stop()
            if self.camera_thread and self.camera_thread.is_alive():
                self.camera_thread.join(timeout=2)
            self.camera_inference_started = False

    def handle_system_settings(self, payload):
        pass
        # try:
        #     self.settings.update(data=json.loads(payload))
        #     self.thermal_camera.set_refresh_rate(self.settings.worm_refresh_rate)
        # except ValueError:
        #     logging.warning(f"Ignored invalid status value: {payload}")
