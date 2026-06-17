import time
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_bytes_per_sec: int):
        self.max_bytes_per_sec = max_bytes_per_sec
        self.client_bytes = defaultdict(int)
        self.last_reset = time.time()

    def check_limit(self, client_id: str, bytes_amount: int) -> bool:
        now = time.time()
        # Reset counters every second
        if now - self.last_reset >= 1.0:
            self.client_bytes.clear()
            self.last_reset = now

        self.client_bytes[client_id] += bytes_amount
        if self.client_bytes[client_id] > self.max_bytes_per_sec:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            return False
        return True
