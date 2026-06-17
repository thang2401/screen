import queue
from typing import Dict, Any

class GlobalStateManager:
    """
    Thread-safe Data Bus connecting Asyncio WebSockets, FastAPI REST, and PyQt6 GUI.
    """
    def __init__(self):
        # queue.Queue is natively thread-safe in Python. 
        # Using it to pass Image Frames from Asyncio -> Main UI Thread.
        self.gui_queue = queue.Queue(maxsize=1000)
        
        # Using it to pass raw JSON strings directly to the Web Dashboard
        self.web_queue = queue.Queue(maxsize=1000)
        
        # Dictionary for API reading
        self.client_states: Dict[str, Dict[str, Any]] = {}
        
    def update_client_state(self, client_id: str, **kwargs):
        if client_id not in self.client_states:
            self.client_states[client_id] = {"is_online": True, "fps": 0, "last_seen": ""}
        self.client_states[client_id].update(kwargs)

    def get_clients(self):
        return self.client_states

# Singleton instance
global_state = GlobalStateManager()
