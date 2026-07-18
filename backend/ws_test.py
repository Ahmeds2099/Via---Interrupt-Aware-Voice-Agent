import asyncio
import json
# pyrefly: ignore [missing-import]
import websockets


async def main():
    async with websockets.connect(
        "ws://127.0.0.1:8000/ws/voice"
    ) as ws:

        print(await ws.recv())

        await ws.send(json.dumps({"type": "ping"}))

        print(await ws.recv())

        await ws.send(b"\x00" * 320)

        print("Binary frame sent.")


asyncio.run(main())