import warnings
# Ignore the warning raised by dspy until it is fixed
warnings.filterwarnings('ignore', message='Valid config keys have changed in V2', category=UserWarning)
import asyncio
import dspy
from dotenv import load_dotenv
import os
import openlit
from eggai import eggai_main
from eggai.transport import eggai_set_default_transport, KafkaTransport
from .agent import billing_agent


@eggai_main
async def main():
    load_dotenv()
    openlit.init(
        application_name="billing_agent",
        otlp_endpoint=os.getenv("OTEL_ENDPOINT"),
        disabled_instrumentors=["langchain"],
    )
    language_model = dspy.LM("openai/gpt-4o-mini", cache=False)
    dspy.configure(lm=language_model)
    eggai_set_default_transport(lambda: KafkaTransport())
    await billing_agent.start()

    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
