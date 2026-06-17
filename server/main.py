import asyncio
import logging
import sys
from server.network.socket_server import SocketServer
from server.ai.detector_engine import DetectorEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def main():
    HOST = "0.0.0.0"
    PORT = 8765
    SECRET_KEY = b"0123456789abcdef0123456789abcdef" 
    
    server = SocketServer(host=HOST, port=PORT, secret_key=SECRET_KEY)
    ai_engine = DetectorEngine(frame_queue=server.frame_queue, detection_interval=2.0)
    
    # Start AI Engine
    await ai_engine.start()
    
    # Start WebSockets
    try:
        await server.start()
    except KeyboardInterrupt:
        logging.info("Shutting down server...")
    finally:
        ai_engine.stop()

if __name__ == "__main__":
    asyncio.run(main())
