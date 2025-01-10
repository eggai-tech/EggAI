import os
import uvicorn
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse

from websocket_agent import plug_fastapi_websocket, start_websocket_gateway, stop_websocket_gateway

api = FastAPI()
config = uvicorn.Config(api, host="127.0.0.1", port=8000, log_level="info")
server = uvicorn.Server(config)


@api.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "chat.html")
        if not os.path.isfile(html_file_path):
            raise FileNotFoundError(f"chat.html not found at {html_file_path}")
        with open(html_file_path, "r", encoding="utf-8") as file:
            file_content = file.read()

        return HTMLResponse(content=file_content, status_code=200)

    except FileNotFoundError as fnf_error:
        raise HTTPException(status_code=404, detail=str(fnf_error))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

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