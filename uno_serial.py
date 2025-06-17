import threading
from time import sleep

try:
    from utils import *
    from broker_publisher import MQTTPublisherThread
    from base_serial import BaseSerialProcessor
    from constants import *
except ImportError:
    logging.errro("Required modules could not be imported.")
    raise

class UnoSerialProcessor(BaseSerialProcessor):
    def __init__(self, port, baud, mqtt_client):
        super().__init__(port, baud)
        self.mqtt_client = mqtt_client
        self.mqtt_publisher = MQTTPublisherThread(mqtt_client)
        self.mqtt_publisher.start()
        
    # [✅]
    def handle_message(self, msg):
        if msg.startswith("P"):
            print(f"[Uno] <P command> {msg}")
            
        elif any(msg.startswith(prefix) for prefix in ["info:", "warn", "error:", "fatal:"]):
            self.handle_log_message(msg)

        else:
            self.log("error", f"Unknown command: {msg}")
            
    # [✅]
    def handle_log_message(self, message):
        try:
            parts = message.split(":", 1)
            log_type = parts[0]
            content = parts[1] if len(parts) > 1 else ""
            
            self.log(log_type, content)

            self.mqtt_publisher.publish(f"system/log", message, qos=1)
            
            # threading.Thread(target=self.send_request(log_type, content), name="handle_log_message", daemon=True).start()

        except Exception as e:
            self.log("error", f"Failed to handle log message: {e}")