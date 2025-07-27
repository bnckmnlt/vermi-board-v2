import threading
from queue import Queue


class MQTTPublisherThread(threading.Thread):
    def __init__(self, mqtt_client):
        super().__init__(daemon=True)
        self.client = mqtt_client
        self.queue = Queue()

    def run(self):
        while True:
            topic, payload, qos, retain = self.queue.get()
            try:
                self.client.publish(topic, payload, qos=qos, retain=retain)
            except Exception as e:
                print(f"MQTT Publish Error: {e}")

    def publish(self, topic, payload, qos=0, retain=False):
        self.queue.put((topic, payload, qos, retain))
