import asyncio
import websockets

async def test():
    try:
        async with websockets.connect("ws://192.168.1.16:8765/ws/may_29") as ws:
            print("Connected to server successfully!")
            await asyncio.sleep(1)
            print("Sleeping done.")
    except Exception as e:
        print(f"Error: {type(e).__name__} - {e}")

asyncio.run(test())
