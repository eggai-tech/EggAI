import uvicorn
from fastapi import FastAPI

from websocket_agent import plug_fastapi_websocket, start_websocket_gateway, stop_websocket_gateway

api = FastAPI()
config = uvicorn.Config(api, host="127.0.0.1", port=8000, log_level="info")
server = uvicorn.Server(config)


@api.get("/")
async def read_root():
    return {"Hello": "Gateway"}

plug_fastapi_websocket("/ws", api)

# Hook for server startup
@api.on_event("startup")
async def on_startup():
    print("Starting WebSocket gateway...")
    await start_websocket_gateway()

# Hook for server shutdown
@api.on_event("shutdown")
async def on_shutdown():
    print("Stopping WebSocket gateway...")
    await stop_websocket_gateway()