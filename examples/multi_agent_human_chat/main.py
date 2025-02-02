import asyncio

import dspy
from dotenv import load_dotenv
from eggai.hooks import eggai_set_conf

from billing_agent import billing_agent
from escalation_agent import escalation_agent
from policies_agent import policies_agent
from server import server
from triage_agent import triage_agent


async def main():
    load_dotenv()
    await eggai_set_conf({
        "run_forever_auto": False
    })

    language_model = dspy.LM("openai/gpt-4o-mini", cache=False)
    dspy.configure(lm=language_model)

    # UNCOMMENT THIS IF YOU WANT TO RUN IT WITH KAFKA
    # eggai_set_default_transport(lambda: KafkaTransport())

    await policies_agent.start()
    await escalation_agent.start()
    await billing_agent.start()
    await triage_agent.start()
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
