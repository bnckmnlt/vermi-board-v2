import logging
from src.lib.constants import CONTROL_TOPICS


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info("MQTT connected successfully, subscribing to control topics…")
        
        for topic in CONTROL_TOPICS:
            client.subscribe(topic, qos=1)
            logging.debug(f"Subscribed to {topic}")
    else:
        logging.error(f"Failed to connect to MQTT broker, rc={rc}")

def on_disconnect(client, userdata, rc, properties=None):
    logging.warning(f"Disconnected with result code {rc}")
    if rc != 0:
        try:
            logging.info("Attempting to reconnect...")
            client.reconnect()
        except Exception as e:
            logging.error(f"Reconnect failed: {e}")

def on_publish(client, userdata, mid, properties=None):
    pass
    # print("mid: " + str(mid))

def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    pass
    # print("Subscribed: " + str(mid) + " " + str(granted_qos))