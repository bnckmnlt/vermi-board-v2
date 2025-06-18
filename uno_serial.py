import logging

from base_serial import BaseSerialProcessor
from broker_publisher import MQTTPublisherThread

class UnoSerialProcessor(BaseSerialProcessor):
    def __init__(self, port, baud, mqtt_client):
        publisher = MQTTPublisherThread(mqtt_client)
        publisher.start()
        super().__init__(port, baud, mqtt_publisher=publisher)

    def handle_message(self, msg):
        if msg.startswith("P"):
            self.log_async("info", f"[Uno] <P command> {msg}")

        elif any(msg.startswith(pref) for pref in ("info:", "warn:", "error:", "fatal:")):
            self._queue_log(msg)

        else:
            self.log_async("error", f"Unknown command: {msg}")

    def _queue_log(self, message):
        level, _, content = message.partition(":")
        self.log_async(level, content.strip())
