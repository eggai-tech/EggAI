import uvicorn
from fastapi import FastAPI

from gateway.websocket_agent import plug_fastapi_websocket

api = FastAPI()
config = uvicorn.Config(api, host="127.0.0.1", port=8000, log_level="info")
server = uvicorn.Server(config)


@api.get("/")
async def read_root():
    return {"Hello": "Gateway"}

plug_fastapi_websocket("/ws", api)
