import asyncio

import dspy.streaming
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from opentelemetry.propagate import TraceContextTextMapPropagator

from agents.triage.config import settings
from agents.triage.dspy_modules.small_talk import chatty
from agents.triage.models import (
    AGENT_REGISTRY,
    ClassifierVersion,
    TargetAgent,
)
from libraries.channels import channels
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.streaming_agent import format_conversation, process_request_stream
from libraries.tracing import TracedMessage, get_tracer, traced_handler
from libraries.tracing.init_metrics import init_token_metrics

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content,
    )
)

triage_agent = Agent(name="TriageAgent")
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
agents_channel = Channel(channels.agents)

tracer = get_tracer("triage_agent")
logger = get_console_logger("triage_agent.handler")


def get_current_classifier():
    if settings.classifier_version == ClassifierVersion.v0:
        from agents.triage.dspy_modules.classifier_v0 import classifier_v0

        return classifier_v0
    if settings.classifier_version == ClassifierVersion.v1:
        from agents.triage.dspy_modules.classifier_v1 import classifier_v1

        return classifier_v1
    elif settings.classifier_version == ClassifierVersion.v2:
        from agents.triage.dspy_modules.classifier_v2.classifier_v2 import classifier_v2

        return classifier_v2
    elif settings.classifier_version == ClassifierVersion.v3:
        from agents.triage.baseline_model.classifier_v3 import classifier_v3

        return classifier_v3
    elif settings.classifier_version == ClassifierVersion.v4:
        from agents.triage.dspy_modules.classifier_v4 import classifier_v4

        return classifier_v4
    elif settings.classifier_version == ClassifierVersion.v5:
        from agents.triage.attention_net.classifier_v5 import classifier_v5

        return classifier_v5
    else:
        raise ValueError(
            f"Unknown classifier version: {settings.classifier_version.value}"
        )


current_classifier = get_current_classifier()


async def process_triage_request(
    chat_messages: list[dict],
    connection_id: str,
    message_id: str,
) -> None:
    """Classify the conversation and either route or stream a response."""
    formatted_messages = [
        {"role": m.get("agent", m.get("role", "User")), "content": m.get("content", "")}
        for m in chat_messages
    ]
    conversation_string = format_conversation(
        formatted_messages, tracer=tracer, logger=logger
    )

    with tracer.start_as_current_span("process_triage_request") as span:
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        child_traceparent = carrier.get("traceparent")
        child_tracestate = carrier.get("tracestate", "")

        response = current_classifier(chat_history=conversation_string)
        target_agent = response.target_agent

        logger.info(
            "Classification completed in %.2f ms, target agent: %s, classifier version: %s",
            response.metrics.latency_ms,
            target_agent,
            settings.classifier_version.value,
        )

        triage_to_agent_messages = [
            {"role": "user", "content": f"{conversation_string} \n{target_agent}: "}
        ]

        if target_agent != TargetAgent.ChattyAgent:
            with tracer.start_as_current_span("publish_to_agent") as publish_span:
                carrier = {}
                TraceContextTextMapPropagator().inject(carrier)
                pub_parent = carrier.get("traceparent")
                pub_state = carrier.get("tracestate", "")
                await agents_channel.publish(
                    TracedMessage(
                        type=AGENT_REGISTRY[target_agent]["message_type"],
                        source="TriageAgent",
                        data={
                            "chat_messages": triage_to_agent_messages,
                            "message_id": message_id,
                            "connection_id": connection_id,
                        },
                        traceparent=pub_parent,
                        tracestate=pub_state,
                    )
                )
        else:
            chunks = chatty(chat_history=conversation_string)

            await process_request_stream(
                chunks,
                agent_name="TriageAgent",
                connection_id=connection_id,
                message_id=message_id,
                human_stream_channel=human_stream_channel,
                tracer=tracer,
                logger=logger,
                child_traceparent=child_traceparent,
                child_tracestate=child_tracestate,
            )


@triage_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda msg: msg.get("type") == "user_message",
    auto_offset_reset="latest",
    group_id="triage_agent_group",
)
@traced_handler("handle_user_message")
async def handle_user_message(msg: TracedMessage):
    try:
        chat_messages = msg.data.get("chat_messages", [])
        connection_id = msg.data.get("connection_id", "unknown")

        logger.info(f"Received message from connection {connection_id}")

        await process_triage_request(chat_messages, connection_id, str(msg.id))

    except ValueError as exc:
        logger.warning("Invalid triage message: %s", exc, exc_info=True)
    except (ConnectionError, asyncio.TimeoutError) as exc:
        logger.error("Network error in TriageAgent: %s", exc, exc_info=True)
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)


@triage_agent.subscribe(channel=human_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)


if __name__ == "__main__":

    async def run():
        print("Testing chunked chatty:")
        chunks = chatty(chat_history="User: Hello!")
        async for chunk in chunks:
            if isinstance(chunk, dspy.streaming.StreamResponse):
                print(chunk.chunk, end="")
            elif isinstance(chunk, dspy.Prediction):
                print("")
                print(chunk.get_lm_usage())

    asyncio.run(run())
