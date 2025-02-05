import asyncio
import os
from contextlib import asynccontextmanager

import dspy
import uvicorn
from dotenv import load_dotenv
from eggai import eggai_main, eggai_cleanup
from eggai.transport import eggai_set_default_transport, KafkaTransport
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse

from agents.billing_agent import billing_agent
from agents.escalation_agent import escalation_agent
from agents.policies_agent import policies_agent
from agents.triage.agent import triage_agent
from agents.websocket_gateway_agent import (
    add_websocket_gateway,
    websocket_gateway_agent, websocket_manager,
)

api = FastAPI()

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

server = uvicorn.Server(
    uvicorn.Config(api, host="127.0.0.1", port=8000, log_level="info")
)

add_websocket_gateway("/ws", api, server)

@eggai_main
async def main():
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini", cache=False)
    dspy.configure(lm=language_model)

    # eggai_set_default_transport(lambda: KafkaTransport())
    await websocket_gateway_agent.start()
    await policies_agent.start()
    await escalation_agent.start()
    await billing_agent.start()
    await triage_agent.start()
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
