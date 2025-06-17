import json
from concurrent.futures import ThreadPoolExecutor
import queue
import threading

try:
    from utils import *
    from broker_publisher import MQTTPublisherThread
    from base_serial import BaseSerialProcessor
    from constants import DEFAULT_LAYERS
except ImportError:
    logging.error("Required modules could not be imported.")
    raise


class MegaSerialProcessor(BaseSerialProcessor):
    def __init__(self, port, baud, mqtt_client):
        super().__init__(port, baud)
        self.mqtt_client = mqtt_client
        self.mqtt_publisher = MQTTPublisherThread(mqtt_client)
        self.mqtt_publisher.start()

        self.log_queue = queue.Queue()

        # self.consumer_thread = threading.Thread(target=self.process_log_messages, name="process_log_messages", daemon=True).start()
        
    # [✅]
    def handle_message(self, msg):
        if msg.startswith("P"):
            layers = self.handle_p_command(msg)
            
            for layer in ["bedding", "compost", "fluid"]:
                layer_data = json.dumps(layers.get(layer, {}))
                self.mqtt_publisher.publish(f"layer/{layer}", layer_data, qos=1)

            self.evaluate_health_in_thread(layers)

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

            # self.log_queue.put((log_type, content))

            # if "Relay FB" in content:
            #     _, board_str, pin_str, state_str = content.split(":")
            #     board = int(board_str)
            #     pin = int(pin_str)
            #     state = int(state_str)

            #     topic = f"feedback/relay/{board}/{pin}"
            #     self.mqtt_publisher.publish(topic, state, qos=1, retain=True)

        except Exception as e:
            self.log("error", f"Failed to handle log message: {e}")
    
    # [✅]
    def process_log_messages(self):
        while True:
            try:
                log_type, content = self.log_queue.get()

                self.send_request(log_type, content)

                self.log_queue.task_done()

            except Exception as e:
                self.log("error", f"Failed to process log message: {e}")
    
    # [✅]
    def handle_p_command(self, msg):
        try:
            msg = msg.replace("Payload:", "", 1).strip()
            return json.loads(msg).get("layers", DEFAULT_LAYERS)
        except json.JSONDecodeError as e:
            self.log("error", f"Invalid format for P command: {e}")
            return DEFAULT_LAYERS
        
    # [✅]        
    def evaluate_health_in_thread(self, layers):
        health = evaluate_health(layers)
        self.mqtt_publisher.publish("system/health", json.dumps(health), qos=1)
        

    