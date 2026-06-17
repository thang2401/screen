import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConnectionPool:
    def __init__(self):
        self.active_connections: Dict[str, Any] = {}
        
    async def connect(self, client_id: str, ws: Any):
        self.active_connections[client_id] = ws
        logger.debug(f"Added {client_id} to connection pool. Total: {len(self.active_connections)}")
        
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.debug(f"Removed {client_id} from connection pool. Total: {len(self.active_connections)}")
            
    async def broadcast(self, message: bytes):
        for client_id, ws in self.active_connections.items():
            try:
                await ws.send(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")

    async def send_to_client(self, client_id: str, message: bytes):
        if client_id in self.active_connections:
            ws = self.active_connections[client_id]
            try:
                await ws.send(message)
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
