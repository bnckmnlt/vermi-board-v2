import logging
import queue
import serial
import requests
from queue import Queue
from threading import Event, Thread
from time import sleep
from concurrent.futures import ThreadPoolExecutor


class BaseSerialProcessor:
    def __init__(self, port="/dev/ttyUSB0", baud=9600, connection=None):
        self.port = port
        self.baud = baud
        self.serial_conn = connection
        self.message_queue = Queue(maxsize=200)
        self.log_queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.running = True

        self.receive_thread = None
        self.process_serial_thread = None

        self.stop_event = Event()

        if self.serial_conn is None:
            self.init_serial_connection()

    def init_serial_connection(self):
        try:
            self.serial_conn = serial.Serial(
                self.port,
                self.baud,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            if self.serial_conn.is_open:
                logging.info(f"Serial port {self.port} opened successfully.")
            else:
                logging.error(f"Could not open serial port {self.port}")
        except serial.SerialException as e:
            logging.error(f"Serial Error on {self.port}: {e}")

    def recv_with_start_end_markers(self):
        # while self.running:
        while not self.stop_event.is_set():
            try:
                line = self.serial_conn.read_until(b">").decode("utf-8", errors="ignore")
                if "<" in line:
                    start = line.find("<")
                    end = line.find(">", start)
                    if end != -1:
                        msg = line[start + 1:end].strip()
                        self.message_queue.put(msg)
            except Exception as e:
                logging.error(f"Decode error: {e}")
            sleep(0.001)

    def start(self):
        self.receive_thread = Thread(target=self.recv_with_start_end_markers, name="recv_with_start_end_markers", daemon=True).start()
        self.process_serial_thread = Thread(target=self.process_serial_data, name="process_serial_data", daemon=True).start()
        # Thread(target=self.process_log_queue, name="process_log_queue", daemon=True).start()

    def stop(self):
        # self.running = False

        self.stop_event.set()

        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)

        if self.process_serial_thread and self.process_serial_thread.is_alive():
            self.process_serial_thread.join(timeout=2)

        logging.info("All threads have been joined. System stopped.")


    def process_serial_data(self):
        # while self.running:
        while not self.stop_event.is_set():
            try:
                msg = self.message_queue.get(timeout=0.1)
                self.handle_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error in process_serial_data: {e}")

    def process_log_queue(self):
        # while self.running:
        while not self.stop_event.is_set():
            try:
                log_type, content = self.log_queue.get(timeout=0.5)
                self.executor.submit(self.send_request, log_type, content)
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error in process_log_queue: {e}")

    def log_async(self, log_type, content):
        try:
            self.log_queue.put_nowait((log_type, content))
        except queue.Full:
            logging.warning("Log queue full, dropping log")

    def handle_message(self, msg):
        raise NotImplementedError("You must implement handle_message() in a subclass.")

    def send_data(self, data):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(data.encode())
                print(f"Data sent to {self.port}: {data}")
            except serial.SerialException as e:
                print(f"Error sending data to {self.port}: {e}")
        else:
            print(f"Serial connection {self.port} not open or invalid.")

    def send_request(self, log_type, content):
        try:
            url = "https://verminator.thinkio.me/logs"
            data = {
                "eventSeverity": str(log_type),
                "eventMessage": str(content),
            }
            response = requests.post(
                url,
                json=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=5
            )
            logging.info(f"[{response.status_code}] {response.url:6s} - {response.text}")
        except Exception as e:
            logging.error(f"Error sending data to server: {e}")

    def log(self, log_type: str, content: str):
        log_type = log_type.lower()
        message = f"{self.__class__.__name__} - {content}"

        log_levels = {
            'debug': logging.debug,
            'info': logging.info,
            'warning': logging.warning,
            'error': logging.error,
            'fatal': logging.critical
        }

        log_func = log_levels.get(log_type, logging.info)
        log_func(message)
