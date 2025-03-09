import warnings

# Ignore the warning raised by dspy until it is fixed
warnings.filterwarnings(
    "ignore", message="Valid config keys have changed in V2", category=UserWarning
)
import asyncio
import dspy
import os
from dotenv import load_dotenv
from eggai import eggai_main
from eggai.transport import eggai_set_default_transport, KafkaTransport
from agents.tracing import init_telemetry
from .agent import triage_agent


@eggai_main
async def main():
    load_dotenv()
    init_telemetry(app_name="triage_agent")
    language_model = dspy.LM("openai/gpt-4o-mini", cache=False)
    dspy.configure(lm=language_model)
    eggai_set_default_transport(lambda: KafkaTransport())
    await triage_agent.start()

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
