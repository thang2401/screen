import asyncio
import logging
import sys
from client.service import ClientService

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def main():
    # Nhận IP máy chủ từ lệnh chạy (nếu có), mặc định là localhost
    server_ip = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    SERVER_URL = f"ws://{server_ip}:8765"
    
    # Use a dummy 32-byte key for development
    SECRET_KEY = b"0123456789abcdef0123456789abcdef" 
    
    # Nhận client_id từ đối số dòng lệnh nếu có (ví dụ: python run_client.py may_01)
    custom_client_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    service = ClientService(server_url=SERVER_URL, secret_key=SECRET_KEY, client_id=custom_client_id)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logging.info("Shutting down client...")
    finally:
        await service.ws_client.stop()

if __name__ == "__main__":
    asyncio.run(main())
