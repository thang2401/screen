import asyncio
import websockets
import logging
import json
from datetime import datetime
from server.network.connection_pool import ConnectionPool
from server.network.rate_limiter import RateLimiter
from core.protocol import Protocol
from core.crypto_manager import CryptoManager
from core.constants import CommandTypes
from core.compression import CompressionManager
from core.state import global_state

logger = logging.getLogger(__name__)

class SocketServer:
    def __init__(self, host: str, port: int, secret_key: bytes):
        self.host = host
        self.port = port
        self.pool = ConnectionPool()
        self.crypto = CryptoManager(secret_key)
        self.frame_queue = None
        self.rate_limiter = RateLimiter(max_bytes_per_sec=50_000_000) # 50MB/s per client limit

    async def handle_client(self, websocket, path=None):
        # Tương thích ngược với websockets >= 14.0 (chỉ truyền 'websocket')
        if path is None:
            request = getattr(websocket, 'request', None)
            path = getattr(request, 'path', '') if request else getattr(websocket, 'path', '')
            
        client_id = path.strip('/').split('/')[-1]
        
        if not client_id or client_id == "ws":
            logger.error(f"Invalid client path connection: {path}")
            return

        await self.pool.connect(client_id, websocket)
        global_state.update_client_state(client_id, is_online=True, last_seen=datetime.utcnow().isoformat())
        logger.info(f"Client connected: {client_id}")

        try:
            async for message in websocket:
                if not self.rate_limiter.check_limit(client_id, len(message)):
                    continue
                global_state.update_client_state(client_id, last_seen=datetime.utcnow().isoformat())
                await self.process_message(client_id, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Unexpected error handling client {client_id}: {e}")
        finally:
            self.pool.disconnect(client_id)
            global_state.update_client_state(client_id, is_online=False)
            try:
                global_state.gui_queue.put_nowait((client_id, None))
                global_state.web_queue.put_nowait((client_id, None))
            except Exception:
                pass

    async def process_message(self, client_id: str, message: bytes):
        cmd_type, length = Protocol.unpack_header(message)
        if cmd_type is None:
            return

        payload = message[Protocol.HEADER_SIZE:]
        try:
            decrypted = self.crypto.decrypt(payload)
            
            if cmd_type == CommandTypes.SCREEN_FRAME:
                decompressed = CompressionManager.decompress_zlib(decrypted)
                json_str = decompressed.decode('utf-8')
                
                # Zero-copy forwarding: send raw JSON straight to Web Dashboard
                try:
                    global_state.web_queue.put_nowait((client_id, json_str))
                except Exception:
                    pass
                
                data = json.loads(json_str)
                
                if not self.frame_queue.full():
                    await self.frame_queue.put(data)
                else:
                    logger.debug("Frame queue is full, dropping frame")
            
            elif cmd_type == CommandTypes.HEARTBEAT:
                logger.debug(f"Heartbeat from {client_id}")
                
        except Exception as e:
            logger.error(f"Error processing message from {client_id}: {e}")

    async def send_to_client(self, client_id: str, message: bytes):
        await self.pool.send_to_client(client_id, message)

    async def start(self):
        if self.frame_queue is None:
            self.frame_queue = asyncio.Queue(maxsize=1000)
        logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port, max_size=None, ping_interval=20, ping_timeout=20):
            await asyncio.Future()  # run forever
