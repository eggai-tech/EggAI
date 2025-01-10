import asyncio
import json

import websockets
from eggai import Channel

from coordinator import start_coordinator, stop_coordinator
from email_agent import start_email_agent, stop_email_agent
from gateway.server import server
from order_agent import start_order_agent, stop_order_agent

async def main():
    await start_email_agent()
    await start_order_agent()
    await start_coordinator()

    server_task = asyncio.create_task(server.serve())
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        reply = await websocket.recv()
        print(f"Connection id: {reply}")
        message = {
            "type": "create_order",
            "payload": {
                "product": "Laptop",
                "quantity": 3
            }
        }
        await websocket.send(json.dumps(message))
        reply = await websocket.recv()
        print(f"Message id: {json.loads(reply)['id']}")

        reply = await websocket.recv()
        print(f"Reply: {reply}")

        await websocket.close()

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await stop_coordinator()
        await stop_email_agent()
        await stop_order_agent()
        await Channel.stop()
        server_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
