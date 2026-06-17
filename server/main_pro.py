import sys
import os

# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import threading
import logging
import uvicorn
import signal
import time
import cv2
import base64
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from server.network.socket_server import SocketServer
from server.ai.detector_engine import DetectorEngine
from server.database.db_manager import db_manager
from server.api.routes import router as api_router
from core.state import global_state
from core.protocol import Protocol
from core.crypto_manager import CryptoManager
from core.constants import CommandTypes

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("SystemCore")

# FastAPI Configuration
app = FastAPI(title="Screen Monitor Pro API")
app.include_router(api_router)

# --- WEB DASHBOARD ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def get_web_dashboard():
    html_path = "server/index.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Web Dashboard chưa được tạo. Vui lòng tạo file server/index.html</h1>"

@app.get("/ping")
@app.head("/ping")
async def ping():
    return {"status": "ok"}

@app.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket):
    await websocket.accept()
    ws_server = getattr(websocket.app.state, 'ws_server', None)
    async_loop = getattr(websocket.app.state, 'async_loop', None)
    
    if not ws_server:
        await websocket.close()
        return

    try:
        while True:
            # Nhận lệnh điều khiển từ Admin Web
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            target_id = payload.get("target_id")
            if target_id:
                # Bọc payload để Client xử lý đúng theo logic `command_handler`
                client_payload = {
                    "command": payload.get("action"),
                    "params": payload.get("data", {})
                }
                
                # Mã hóa và gửi xuống máy con bằng giao thức nội bộ
                crypto = CryptoManager(SECRET_KEY)
                json_data = json.dumps(client_payload).encode('utf-8')
                encrypted = crypto.encrypt(json_data)
                
                # Sử dụng UPDATE_CONFIG làm command trung chuyển chung
                packet = Protocol.pack(CommandTypes.UPDATE_CONFIG, encrypted)
                
                if async_loop:
                    import asyncio
                    send_func = getattr(ws_server, 'send_to_client', None)
                    if send_func:
                        asyncio.run_coroutine_threadsafe(send_func(target_id, packet), async_loop)
                else:
                    await ws_server.send_to_client(target_id, packet)
                    
    except WebSocketDisconnect:
        logger.info("Admin WS disconnected")
    except Exception as e:
        err_msg = str(e)
        if "1001" in err_msg or "going away" in err_msg or "no close frame" in err_msg:
            logger.info("Admin WS disconnected")
        else:
            logger.error(f"Admin WS error: {e}")

# Hàm xử lý ảnh chuyên dụng chạy trên Thread nền để không làm nghẽn luồng Asyncio
def process_frame_for_web(frame):
    height, width = frame.shape[:2]
    # Cân bằng độ nét và độ mượt: Tăng chiều rộng lên 1600 (HD+)
    if width > 1600:
        scale = 1600 / width
        # Dùng INTER_LINEAR để giữ chi tiết chữ (text) sắc nét hơn khi thu nhỏ
        frame = cv2.resize(frame, (1600, int(height * scale)), interpolation=cv2.INTER_LINEAR)
    
    # Chỉnh JPEG Quality lên 90 để hình ảnh trong trẻo, rõ ràng
    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90, int(cv2.IMWRITE_JPEG_OPTIMIZE), 1])
    return base64.b64encode(buffer).decode('utf-8')

@app.websocket("/ws/web-dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            messages_to_send = []
            
            while not global_state.web_queue.empty():
                client_id, json_str = global_state.web_queue.get_nowait()
                if json_str is None:
                    # Gửi thông báo xoá máy con nếu bị ngắt kết nối theo đúng thứ tự
                    messages_to_send.append(json.dumps({
                        "client_id": client_id,
                        "disconnected": True
                    }))
                else:
                    messages_to_send.append(json_str)
            
            # TỐI ƯU QUY MÔ LỚN: Gom (Batch) tất cả các gói tin trong 16ms vào 1 Mảng JSON duy nhất.
            # Thay vì gửi 1800 gói tin/giây cho 30 máy, Server chỉ gửi 60 gói tin lớn/giây chứa Mảng dữ liệu.
            if messages_to_send:
                batch_payload = "[" + ",".join(messages_to_send) + "]"
                await websocket.send_text(batch_payload)
            
            # Ngủ một chút để không chiếm dụng CPU
            await asyncio.sleep(0.016) 
    except WebSocketDisconnect:
        logger.info("Web client disconnected")
    except Exception as e:
        err_msg = str(e)
        if "1001" in err_msg or "going away" in err_msg or "no close frame" in err_msg:
            logger.info("Web client disconnected")
        else:
            logger.error(f"Web Dashboard WS error: {e}")
# ----------------------------

@app.post("/api/clients/{client_id}/command")
async def send_remote_control_command(client_id: str, request: Request):
    """Cầu nối nhận lệnh điều khiển từ GUI và đẩy qua WebSocket xuống Client."""
    try:
        payload = await request.json()
        
        ws_server = getattr(request.app.state, 'ws_server', None)
        async_loop = getattr(request.app.state, 'async_loop', None)
        
        if ws_server:
            # Khởi tạo bộ mã hóa với cùng Secret Key để bảo mật
            crypto = CryptoManager(SECRET_KEY)
            
            # Đóng gói và mã hóa lệnh chuẩn JSON
            json_data = json.dumps(payload).encode('utf-8')
            encrypted = crypto.encrypt(json_data)
            packet = Protocol.pack(CommandTypes.UPDATE_CONFIG, encrypted)
            
            if async_loop:
                # [QUAN TRỌNG] Xử lý lỗi Cross-Thread Asyncio: 
                # Phải ủy quyền lệnh gửi mạng sang đúng luồng Event Loop của SocketServer (Thread 3)
                import asyncio
                send_func = getattr(ws_server, 'send_to_client', None)
                if send_func:
                    asyncio.run_coroutine_threadsafe(send_func(client_id, packet), async_loop)
                    return {"status": "success", "message": "Command queued safely"}
                else:
                    return {"status": "error", "message": "SocketServer missing send_to_client"}
            else:
                # Đẩy lệnh xuống máy con thông qua đường truyền WebSocket tốc độ cao
                await ws_server.send_to_client(client_id, packet)
                return {"status": "success", "message": "Command sent"}
            
        return {"status": "error", "message": "WS Server not ready"}
    except Exception as e:
        logger.error(f"Command routing error: {e}")
        return {"status": "error", "message": str(e)}

# Global configuration
HOST = "0.0.0.0"
PORT_WS = 8765
PORT_API = 8080
SECRET_KEY = b"0123456789abcdef0123456789abcdef"

class EnterpriseSystem:
    def __init__(self):
        self.ws_server = SocketServer(host=HOST, port=PORT_WS, secret_key=SECRET_KEY)
        app.state.ws_server = self.ws_server
        self.ai_engine = DetectorEngine(frame_queue=None, detection_interval=2.0)
        self.async_loop = None
        self.uvicorn_server = None

    def _run_async_services(self):
        """Thread 3: Runs Asyncio tasks (WebSockets + AI Queue)."""
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        
        # Đăng ký loop vào app.state để API ở Thread 2 có thể mượn luồng giao tiếp chéo an toàn
        app.state.async_loop = self.async_loop
        
        # Init DB schema
        self.async_loop.run_until_complete(db_manager.init_db())
        
        # Create queue inside the correct loop
        self.ws_server.frame_queue = asyncio.Queue(maxsize=1000)
        self.ai_engine.frame_queue = self.ws_server.frame_queue
        
        # Start AI and WS concurrent execution
        self.async_loop.run_until_complete(self.ai_engine.start())
        self.async_loop.run_until_complete(self.ws_server.start())
        
        try:
            self.async_loop.run_forever()
        except Exception as e:
            logger.info("Async loop terminated.")
        finally:
            self.async_loop.close()

    def _run_fastapi(self):
        """Thread 2: Runs the uvicorn HTTP server."""
        config = uvicorn.Config(app=app, host=HOST, port=PORT_API, log_level="error")
        self.uvicorn_server = uvicorn.Server(config)
        self.uvicorn_server.run()

    def start(self):
        """Super Entrypoint: Orchestrates all threads."""
        logger.info("Booting Enterprise Screen Monitoring System...")
        
        # Start Thread 1: Asyncio (WebSocket & AI)
        self.thread_async = threading.Thread(target=self._run_async_services, daemon=True)
        self.thread_async.start()
        
        # Start Thread 2: FastAPI (REST API)
        self.thread_api = threading.Thread(target=self._run_fastapi, daemon=True)
        self.thread_api.start()
        
        logger.info(f"🚀 Web Dashboard đang chạy tại: http://localhost:{PORT_API}")
        
        # Block main thread cho đến khi bị gián đoạn (Ctrl + C)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Nhận lệnh tắt hệ thống (Ctrl+C)")
        
        # Trigger cleanup across all threads
        self.shutdown()

    def shutdown(self):
        """Gracefully shuts down all services to prevent zombies."""
        logger.info("Initiating graceful shutdown...")
        # 1. Stop AI Loop
        if self.ai_engine:
            self.ai_engine.stop()
            
        # 2. Stop Uvicorn
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True
            
        # 3. Stop Asyncio Loop
        if self.async_loop and self.async_loop.is_running():
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            
        logger.info("System successfully shutdown. Goodbye.")

if __name__ == "__main__":
    system = EnterpriseSystem()
    try:
        system.start()
    except KeyboardInterrupt:
        print("\n[Hệ thống] Đã tắt Server an toàn.")
