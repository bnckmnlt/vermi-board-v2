import logging
import cv2
from time import sleep
from threading import Thread
from fastapi import FastAPI
from uvicorn import Server, Config
from dataclasses import dataclass, field
from fastapi.responses import StreamingResponse


@dataclass
class FastAPIApp:
    frame: any = field(init=False)
    
    app: FastAPI = field(init=False)
    uvicorn_server: Server = field(init=False)
    server_thread: Thread = field(init=False)
    
    host: str = "0.0.0.0"
    port: int = 8080
    
    is_running: bool = False

    def __post_init__(self):
        self.app = FastAPI()
        self._register_routes()

    def _register_routes(self):
        @self.app.get("/video_feed")
        def video_feed():
            return StreamingResponse(
                self._frame_generator(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )
            
    def _frame_generator(self):
        while self.is_running:
            if self.frame is not None:
                _, buf = cv2.imencode('.jpg', self.frame)
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n'
                
            sleep(1 / 30)
            
    def start_server(self):
        def _serve():
            config = Config(app=self.app, host=self.host, port=self.port, log_level="info", access_log=False)
            self.uvicorn_server = Server(config)
            self.uvicorn_server.run()
            
        self.server_thread = Thread(target=_serve, name='fast_api_camera_stream', daemon=True)
        self.server_thread.start()
        logging.info("FastAPI server thread started")

    def stop_server(self):
        if not self.is_running:
            return
        
        self.is_running = False
        
        try:
            if hasattr(self, 'uvicorn_server'):
                self.uvicorn_server.should_exit = True

            if hasattr(self, 'server_thread') and self.server_thread.is_alive():
                logging.info("Waiting for server thread to terminate...")
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    logging.warning("Server thread did not terminate within timeout.")
                else:
                    logging.info("FastAPI server thread stopped.")
            else:
                logging.info("No active server thread.")
        except Exception as e:
            logging.error(f"Failed to stop server thread: {e}")
