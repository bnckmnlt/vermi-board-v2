import os
from paho import mqtt
from dotenv import load_dotenv
import paho.mqtt.client as paho


class BrokerService:
    _instance = None
     
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrokerService, cls).__new__(cls)
            cls._instance.client = paho.Client(client_id="raspi_client", userdata=None, protocol=paho.MQTTv5)
            cls._instance._configure_callbacks(
                kwargs.get('on_connect'),
                kwargs.get('on_disconnect'),
                kwargs.get('on_subscribe'),
                kwargs.get('on_publish'),
                kwargs.get('on_message')
            )
        return cls._instance
    
    def _configure_callbacks(self, on_connect, on_disconnect, on_subscribe, on_publish, on_message):
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.on_subscribe = on_subscribe
        self.client.on_publish = on_publish
        self.client.on_message = on_message
        
    def initialize(self):
        try:
            load_dotenv()
            
            username: str = os.getenv("AUTH_USERNAME")
            password: str = os.getenv("AUTH_PASSWORD")
            cluster_url: str = os.getenv("CLUSTER_URL") 
            cluster_port: int = os.getenv("CLUSTER_PORT")
            
            self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
            self.client.username_pw_set(username, password)
            self.client.connect(cluster_url, int(cluster_port), clean_start=mqtt.client.MQTT_CLEAN_START_FIRST_ONLY)

        except Exception as e:
            raise Exception(f"MQTT Client failed to initialize: {e}")
            
    def get_client(self):
        return self.client