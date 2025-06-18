import logging
import queue
import serial
from threading import Event, Thread
from time import sleep, time
from concurrent.futures import ThreadPoolExecutor

class BaseSerialProcessor:
    def __init__(self, port="/dev/ttyUSB0", baud=9600, mqtt_publisher=None):
        self.port = port
        self.baud = baud
        self.serial_conn = None
        self.mqtt_publisher = mqtt_publisher
        self.message_queue = queue.Queue(maxsize=200)
        self.log_queue     = queue.Queue(maxsize=500)
        self.stop_event    = Event()
        self.executor      = ThreadPoolExecutor(max_workers=3)

        self._init_serial_connection()

    def _init_serial_connection(self):
        try:
            self.serial_conn = serial.Serial(
                self.port, self.baud,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            status = "opened" if self.serial_conn.is_open else "failed"
            logging.info(f"{self.port} serial port {status}.")
        except serial.SerialException as e:
            logging.error(f"Serial init error on {self.port}: {e}")

    def start(self):
        Thread(target=self._recv_loop,     daemon=True).start()
        Thread(target=self._serial_loop,   daemon=True).start()
        Thread(target=self._log_publish_loop, daemon=True).start()

    def stop(self):
        self.stop_event.set()

    def _recv_loop(self):
        while not self.stop_event.is_set():
            try:
                raw = self.serial_conn.read_until(b">")
                text = raw.decode("utf-8", errors="ignore")
                if "<" in text and ">" in text:
                    msg = text.split("<", 1)[1].split(">", 1)[0].strip()
                    self.message_queue.put(msg, timeout=0.1)
            except Exception as e:
                logging.error(f"Decode error: {e}")
            sleep(0.001)

    def _serial_loop(self):
        while not self.stop_event.is_set():
            try:
                msg = self.message_queue.get(timeout=0.1)
                self.handle_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Serial processing error: {e}")

    def _log_publish_loop(self):
        last_pub = 0
        min_interval = 0.2
        while not self.stop_event.is_set():
            try:
                log_type, content = self.log_queue.get(timeout=0.5)
                now = time()
                if now - last_pub < min_interval:
                    sleep(min_interval - (now - last_pub))
                if self.mqtt_publisher:
                    self.mqtt_publisher.publish("system/log", f"{log_type}: {content}", qos=0)
                last_pub = time()
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Logging error: {e}")

    def log_async(self, level, msg):
        try:
            self.log_queue.put_nowait((level.lower(), msg))
        except queue.Full:
            logging.warning("Dropped log — queue full")

    def handle_message(self, msg):
        raise NotImplementedError("Subclass must implement handle_message()")
