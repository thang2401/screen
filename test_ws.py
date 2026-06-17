import asyncio
import websockets
import sys

class SocketServer:
    async def handle_client(self, websocket, path):
        print(f"Connected: {path}")

    async def start(self):
        print(f"websockets version: {websockets.__version__}")
        async with websockets.serve(self.handle_client, "127.0.0.1", 8765):
            print("Server listening")
            await asyncio.Future()

async def main():
    s = SocketServer()
    asyncio.create_task(s.start())
    
    # wait a bit for server to start
    await asyncio.sleep(1)
    
    # try to connect
    try:
        async with websockets.connect("ws://127.0.0.1:8765/ws/test_client") as ws:
            print("Client connected!")
    except Exception as e:
        print(f"Client error: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(main())
