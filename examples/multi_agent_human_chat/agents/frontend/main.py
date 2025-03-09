import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from eggai import eggai_cleanup
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse
from eggai.transport import eggai_set_default_transport, KafkaTransport
from agents.tracing import init_telemetry

from .agent import (
    add_websocket_gateway,
    frontend_agent,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        eggai_set_default_transport(lambda: KafkaTransport())
        await frontend_agent.start()
        yield
    finally:
        await eggai_cleanup()


api = FastAPI(lifespan=lifespan)


@api.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "public/index.html")
        if not os.path.isfile(html_file_path):
            raise FileNotFoundError("File not found")
        with open(html_file_path, "r", encoding="utf-8") as file:
            file_content = file.read()

        return HTMLResponse(content=file_content, status_code=200)

    except FileNotFoundError as fnf_error:
        raise HTTPException(status_code=404, detail=str(fnf_error))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


frontend_server = uvicorn.Server(
    uvicorn.Config(api, host="127.0.0.1", port=8000, log_level="info")
)

add_websocket_gateway("/ws", api, frontend_server)

if __name__ == "__main__":
    load_dotenv()
    init_telemetry(app_name="frontend_agent")
    asyncio.run(frontend_server.serve())
