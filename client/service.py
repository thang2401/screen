import asyncio
import logging
import uuid
import time
from client.capture_optimized import ScreenCapture
from client.encoder import FrameEncoder
from client.ws_client import WSClient
from core.constants import CommandTypes
from core.protocol import Protocol
from core.crypto_manager import CryptoManager

logger = logging.getLogger(__name__)

class ClientService:
    def __init__(self, server_url: str, secret_key: bytes, client_id: str = None):
        self.client_id = client_id if client_id else str(uuid.uuid4())
        self.server_url = server_url
        # Connect to specific endpoint for screen streaming
        self.ws_client = WSClient(f"{server_url}/ws/{self.client_id}")
        self.capture = ScreenCapture()
        self.encoder = FrameEncoder(secret_key)
        self.crypto = CryptoManager(secret_key)
        
        self.ws_client.set_handler(self.handle_message)
        self.fps_target = 60 # TĂNG LÊN 60 FPS: Độ mượt tối đa nhờ chuyển sang JPEG và Web Canvas Rendering
        self.frame_interval = 1.0 / self.fps_target
        
        from client.handlers.command_handler import CommandHandler
        self.command_handler = CommandHandler(self)

    async def handle_message(self, message: bytes):
        # Decode server message
        cmd_type, length = Protocol.unpack_header(message)
        if cmd_type is None:
            return
            
        payload = message[Protocol.HEADER_SIZE:]
        try:
            decrypted = self.crypto.decrypt(payload)
            data = Protocol.unpack_json(decrypted)
            
            if cmd_type == CommandTypes.LOCK:
                logger.info("Received LOCK command")
                await self.command_handler.handle('lock')
            elif cmd_type == CommandTypes.UNLOCK:
                logger.info("Received UNLOCK command")
                await self.command_handler.handle('unlock')
            elif cmd_type == CommandTypes.UPDATE_CONFIG:
                if 'fps' in data:
                    self.fps_target = data['fps']
                    self.frame_interval = 1.0 / self.fps_target
            
            # Xử lý các lệnh điều khiển mở rộng (chuột, phím, v.v.)
            if isinstance(data, dict) and 'command' in data:
                cmd = data.get('command')
                params = data.get('params', {})
                # For direct hardware input commands
                if cmd == 'type_text':
                    await self.command_handler._cmd_type_text(**params)
                else:
                    await self.command_handler.handle(cmd, params)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def stream_frames(self):
        consecutive_errors = 0
        was_connected = False
        while True:
            start_time = time.time()
            if self.ws_client.ws and getattr(self.ws_client.ws, "open", str(getattr(self.ws_client.ws, "state", "")) == "State.OPEN"):
                if not was_connected:
                    # Xóa cache frame cũ để bắt buộc gửi ảnh Full khi mới kết nối lại
                    self.encoder.prev_frame = None
                    was_connected = True
                    
                try:
                    frame = self.capture.capture()
                    encoded_packet = self.encoder.encode_frame(frame, self.client_id)
                    await self.ws_client.send(encoded_packet)
                    consecutive_errors = 0
                except Exception as e:
                    error_str = str(e)
                    if "BitBlt" in error_str:
                        consecutive_errors += 1
                        sleep_time = min(5.0, consecutive_errors * 1.0)
                        logger.warning(f"Màn hình đang khóa, tắt hoặc hiện UAC. Tạm nghỉ {sleep_time}s...")
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        logger.error(f"Error streaming frame: {e}")
                        # Khi mạng lỗi rớt frame, huỷ cache để bắt gửi lại Full Frame ở lần tiếp theo chống vỡ ảnh
                        self.encoder.prev_frame = None
            else:
                was_connected = False
            
            elapsed = time.time() - start_time
            sleep_time = self.frame_interval - elapsed
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0) # Yield lại context để không bóp nghẹt Event Loop khi máy yếu

    async def start(self):
        logger.info(f"Starting ClientService ID: {self.client_id}")
        asyncio.create_task(self.stream_frames())
        await self.ws_client.connect()
