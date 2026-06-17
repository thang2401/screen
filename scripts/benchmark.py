import asyncio
import time
import psutil
import logging
import sys
import numpy as np
import argparse

# Ensure core modules can be imported
sys.path.append('.')

from client.encoder import FrameEncoder
from client.ws_client import WSClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("Benchmark")

class BotSimulator:
    def __init__(self, bot_id: int, server_url: str, secret_key: bytes):
        self.client_id = f"bot-{bot_id}"
        self.ws_client = WSClient(f"{server_url}/ws/{self.client_id}")
        self.encoder = FrameEncoder(secret_key)
        self.running = False
        self.bytes_sent = 0

    async def generate_and_send_frame(self):
        # Simulate an evolving screen: background + a moving noise block
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        step = 0
        while self.running:
            if self.ws_client.ws and self.ws_client.ws.open:
                try:
                    # Move a 200x200 block across the screen
                    x = (step * 50) % (1920 - 200)
                    y = (step * 30) % (1080 - 200)
                    
                    # Create some changes
                    frame[y:y+200, x:x+200] = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
                    
                    encoded_packet = self.encoder.encode_frame(frame, self.client_id)
                    await self.ws_client.send(encoded_packet)
                    self.bytes_sent += len(encoded_packet)
                    
                    step += 1
                except Exception as e:
                    logger.debug(f"Bot {self.client_id} error: {e}")
            
            await asyncio.sleep(0.1) # 10 FPS

    async def start(self):
        self.running = True
        asyncio.create_task(self.generate_and_send_frame())
        await self.ws_client.connect()

    def stop(self):
        self.running = False
        self.ws_client.stop()

async def monitor_resources():
    while True:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        logger.info(f"System Load - CPU: {cpu}% | RAM: {ram}%")
        await asyncio.sleep(2)

async def run_benchmark(num_bots: int, server_url: str, duration: int):
    SECRET_KEY = b"0123456789abcdef0123456789abcdef" 
    bots = []
    
    logger.info(f"Starting benchmark with {num_bots} bots against {server_url}...")
    
    # Start resource monitor
    monitor_task = asyncio.create_task(monitor_resources())
    
    # Init bots
    for i in range(num_bots):
        bot = BotSimulator(i, server_url, SECRET_KEY)
        bots.append(bot)
        asyncio.create_task(bot.start())
        await asyncio.sleep(0.05) # Stagger connections slightly
        
    logger.info("All bots initialized. Running benchmark...")
    
    start_time = time.time()
    await asyncio.sleep(duration)
    
    logger.info("Benchmark complete. Gathering stats...")
    
    total_bytes = sum(bot.bytes_sent for bot in bots)
    total_mb = total_bytes / (1024 * 1024)
    mbps = total_mb / duration
    
    logger.info(f"--- Benchmark Results ---")
    logger.info(f"Total Bots: {num_bots}")
    logger.info(f"Duration: {duration}s")
    logger.info(f"Total Data Sent: {total_mb:.2f} MB")
    logger.info(f"Average Bandwidth: {mbps:.2f} MB/s")
    logger.info(f"Bandwidth per Bot: {(mbps/num_bots)*1024:.2f} KB/s")
    
    # Cleanup
    for bot in bots:
        bot.stop()
    monitor_task.cancel()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load testing tool for Screen Monitor Pro")
    parser.add_argument("--bots", type=int, default=50, help="Number of concurrent bots")
    parser.add_argument("--url", type=str, default="ws://127.0.0.1:8765", help="Server WebSocket URL")
    parser.add_argument("--time", type=int, default=30, help="Duration to run in seconds")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_benchmark(args.bots, args.url, args.time))
    except KeyboardInterrupt:
        logger.info("Benchmark aborted.")
