import json
import logging
from threading import Thread

from src.services.base_serial import BaseSerialProcessor
from src.broker.broker_publisher import MQTTPublisherThread
from src.lib.constants import DEFAULT_LAYERS
from src.lib.utils import evaluate_health

class MegaSerialProcessor(BaseSerialProcessor):
    def __init__(self, port, baud, mqtt_client):
        publisher = MQTTPublisherThread(mqtt_client)
        publisher.start()

        super().__init__(port, baud, mqtt_publisher=publisher)

    def handle_message(self, msg):
        if msg.startswith("P"):
            self._dispatch_payload(msg)
        elif any(msg.startswith(pref) for pref in ("info:", "warn:", "error:", "fatal:")):
            self._queue_log(msg)
        else:
            self.log_async("error", f"Unknown command: {msg}")

    def _dispatch_payload(self, raw):
        payload = raw.replace("Payload:", "", 1).strip()
        try:
            layers = json.loads(payload).get("layers", DEFAULT_LAYERS)
        except json.JSONDecodeError as e:
            logging.error(f"P cmd decode error: {e}")
            layers = DEFAULT_LAYERS

        for layer in ("bedding", "compost", "fluid"):
            data = json.dumps(layers.get(layer, {}))
            self.mqtt_publisher.publish(f"layer/{layer}", data, qos=1)

        health = evaluate_health(layers)
        self.mqtt_publisher.publish("system/health", json.dumps(health), qos=1)

    def _queue_log(self, message):
        level, _, msg = message.partition(":")
        self.log_async(level, msg.strip())
