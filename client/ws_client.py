import asyncio
import websockets
import logging
from typing import Callable, Coroutine

logger = logging.getLogger(__name__)

class WSClient:
    def __init__(self, url: str):
        self.url = url
        self.ws = None
        self.running = False
        self.reconnect_delay = 1
        self.on_message_handler: Callable[[bytes], Coroutine] = None

    def set_handler(self, handler: Callable[[bytes], Coroutine]):
        self.on_message_handler = handler

    async def connect(self):
        self.running = True
        while self.running:
            try:
                logger.info(f"Connecting to {self.url}...")
                async with websockets.connect(self.url, ping_interval=None, max_size=None) as ws:
                    self.ws = ws
                    logger.info("Connected successfully")
                    self.reconnect_delay = 1 # Reset delay on success
                    await self._receive_loop()
            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                logger.error(f"Connection lost/failed: {e}")
                self.ws = None
                await self._exponential_backoff()

    async def _receive_loop(self):
        try:
            async for message in self.ws:
                if self.on_message_handler:
                    await self.on_message_handler(message)
        except Exception as e:
            logger.error(f"Receive loop error: {e}")

    async def _exponential_backoff(self):
        logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
        await asyncio.sleep(self.reconnect_delay)
        self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    async def send(self, data: bytes):
        if self.ws and getattr(self.ws, "open", str(getattr(self.ws, "state", "")) == "State.OPEN"):
            try:
                await self.ws.send(data)
            except Exception as e:
                logger.error(f"Failed to send data: {e}")

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()
