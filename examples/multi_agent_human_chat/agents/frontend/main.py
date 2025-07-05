import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from eggai import eggai_cleanup
from eggai.transport import eggai_set_default_transport
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse

from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

from .agent import add_websocket_gateway, frontend_agent

logger = get_console_logger("frontend_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await frontend_agent.start()
        logger.info(f"{settings.app_name} started successfully")

        yield
    finally:
        logger.info("Cleaning up resources")
        await eggai_cleanup()


api = FastAPI(lifespan=lifespan)


@api.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        html_file_path = os.path.join(settings.default_public_dir, "index.html")
        logger.debug(f"Reading HTML file from: {html_file_path}")

        if not os.path.isfile(html_file_path):
            logger.error(f"File not found: {html_file_path}")
            raise FileNotFoundError(f"File not found: {html_file_path}")

        with open(html_file_path, "r", encoding="utf-8") as file:
            file_content = file.read()

        return HTMLResponse(content=file_content, status_code=200)

    except FileNotFoundError as fnf_error:
        logger.error(f"File not found: {str(fnf_error)}")
        raise HTTPException(status_code=404, detail=str(fnf_error))

    except Exception as e:
        logger.error(f"Error reading HTML: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


frontend_server = uvicorn.Server(
    uvicorn.Config(
        api, host=settings.host, port=settings.port, log_level=settings.log_level
    )
)

add_websocket_gateway(settings.websocket_path, api, frontend_server)

if __name__ == "__main__":
    try:
        logger.info(f"Starting {settings.app_name}")
        init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)
        logger.info(f"Telemetry initialized for {settings.app_name}")

        logger.info(f"Server starting at http://{settings.host}:{settings.port}")
        asyncio.run(frontend_server.serve())
    except KeyboardInterrupt:
        logger.info("Shutting down frontend agent")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
