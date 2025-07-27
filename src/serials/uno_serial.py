import logging

from src.services.base_serial import BaseSerialProcessor
from src.broker.broker_publisher import MQTTPublisherThread

class UnoSerialProcessor(BaseSerialProcessor):
    def __init__(self, port, baud, mqtt_client):
        publisher = MQTTPublisherThread(mqtt_client)
        publisher.start()
        super().__init__(port, baud, mqtt_publisher=publisher)

    def handle_message(self, msg):
        msg = msg.strip()

        if msg.startswith("C:"):
            state = msg.split(":", 1)[1].strip()
            self.log_async("info", f"[Uno] Conveyor state: {state}")
            self.mqtt_publisher.publish("feedback/conveyor", "active" if state == "Active" else "inactive", qos=1, retain=True)

        elif msg.startswith("R:"):
            state = msg.split(":", 1)[1].strip()
            self.log_async("info", f"[Uno] Rake state: {state}")
            self.mqtt_publisher.publish("feedback/rake", "active" if state == "Active" else "inactive", qos=1, retain=True)

        elif any(msg.startswith(prefix) for prefix in ("info:", "warn:", "error:", "fatal:")):
            self._queue_log(msg)

        else:
            self.log_async("error", f"Unknown command: {msg}")


    def _queue_log(self, message):
        level, _, content = message.partition(":")
        self.log_async(level, content.strip())
