import json
import logging
import os
import threading
from time import sleep
from adafruit_mlx90640 import *
from dotenv import load_dotenv
from supabase import create_client, Client

try:
    from constants import *
    from broker_callback import *
    from logger import setup_logger
    from system_model import Status
    from device_info import DeviceInfo
    from system_model import SystemSettings
    from broker_service import BrokerService
    from uno_serial import UnoSerialProcessor
    from mega_serial import MegaSerialProcessor
    from camera_worker import CameraProcessor
    from thermal_camera import ThermalCameraProcessor
    from broker_message_processor import BrokerMessageProcessor        
except ImportError:
    raise ImportError("Error: Required modules could not be imported.")
            
class MainProgram:
    def __init__(self):
        # --- Sensors and Devices ---
        self.settings = SystemSettings()

        # --- Sensors and Devices ---
        load_dotenv()
    
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        supabase: Client = create_client(url, key)
        
        # --- Processing Modules ---
        self.device_info = DeviceInfo()
        self.thermal_camera = ThermalCameraProcessor()
        self.camera = CameraProcessor(
            model_path="best_v1_ncnn_model",
            resolution=(320, 320),
            bucket_client=supabase,
            bucket_name="image"
        )
    
        # --- Broker Init ---
        mqtt_client_manager = BrokerService(
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_subscribe=on_subscribe,
            on_publish=on_publish,
        )
        self.client = mqtt_client_manager.get_client()

        # --- Serial Communication ---
        self.mega = MegaSerialProcessor(MEGA_SERIAL_PORT, MEGA_SERIAL_BAUD, self.client)
        self.uno = UnoSerialProcessor(UNO_SERIAL_PORT, UNO_SERIAL_BAUD, self.client)
        
        # --- Broker Message Routing ---
        message_processor = BrokerMessageProcessor(settings=self.settings, thermal_camera=self.thermal_camera, camera_inference=self.camera, mega=self.mega, uno=self.uno)
        self.client.on_message = message_processor.on_message
        self.client.enable_logger()
        
        # --- MQTT Client Initialization ---
        mqtt_client_manager.initialize()
        self.client.loop_start()

        # --- Threads Initialization ---
        self.device_info_stop = threading.Event()
        self.worm_info_stop = threading.Event()

        self._device_info_started = False

    def send_device_info(self):
        while not self.device_info_stop.is_set():
            try:
                stats = json.dumps(self.device_info.collect_device_info())
                self.client.publish("system/info", stats)
                sleep(self.settings.reading_interval)
            except Exception as e:
                logging.error(f"Error in collecting device info: {e}")

    def send_worm_info(self):
        while not self.worm_info_stop.is_set():
            try:
                data = json.dumps(self.thermal_camera.get_metrics())
                self.client.publish("layer/worms", data)
                sleep(self.settings.reading_interval)
            except Exception as e:
                logging.error(f"Error in collecting worm data: {e}")
        
    def init_main(self):
        last_status = None

        try:
            while True:
                current_status = self.settings.status
                logging.info(f"Current threads: {[t.name for t in threading.enumerate()]}")

                if current_status != last_status:
                    logging.info(f"Status changed: {last_status} → {current_status}")
                    last_status = current_status
                    self._handle_status_change(current_status)

                sleep(1)

        except KeyboardInterrupt:
            logging.info("Shutdown requested by user.")
        finally:
            self.stop()

    def _handle_status_change(self, status):
        if status == Status.ACTIVE and not self._device_info_started:
            logging.info("System is now ACTIVE.")
            self.device_info_stop.clear()
            self.worm_info_stop.clear()

            self.device_info_thread = threading.Thread(target=self.send_device_info, name="send_device_info", daemon=True)
            self.worm_info_thread = threading.Thread(target=self.send_worm_info, name="send_worm_info", daemon=True)

            self.device_info_thread.start()
            self.worm_info_thread.start()
            self._device_info_started = True

        elif status in {Status.FEEDING, Status.IDLE} and self._device_info_started:
            logging.info(f"System is now {status.value.upper()}. Stopping info threads.")
            self.device_info_stop.set()
            self.worm_info_stop.set()

            self.device_info_thread.join(timeout=2)
            self.worm_info_thread.join(timeout=2)
            self._device_info_started = False

    def stop(self):
        logging.info("Stopping program...")

        self.thermal_camera.stop_server()

        self.device_info_stop.set()
        self.worm_info_stop.set()

        self.mega.stop()
        self.uno.stop()

        if self.device_info_thread:
            self.device_info_thread.join(timeout=2)
        if self.worm_info_thread:
            self.worm_info_thread.join(timeout=2)

        self._device_info_started = False

        self.client.loop_stop()
        
        logging.info("Program stopped.")

# --- START ---
if __name__ == "__main__":
    setup_logger()
    start_sys = MainProgram()
    try:
        start_sys.init_main()
        while True:
            sleep(1)
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Shutting down cleanly...")
        start_sys.stop()
