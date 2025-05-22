import asyncio

import dspy.streaming
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from opentelemetry import trace

from agents.triage.config import settings
from agents.triage.dspy_modules.small_talk import chatty
from agents.triage.models import AGENT_REGISTRY, TargetAgent
from libraries.channels import channels
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, format_span_as_traceparent, traced_handler

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

triage_agent = Agent(name="TriageAgent")
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human + "_stream")
agents_channel = Channel(channels.agents)

tracer = trace.get_tracer("triage_agent")
logger = get_console_logger("triage_agent.handler")


def get_current_classifier():
    if settings.classifier_version == "v0":
        from agents.triage.dspy_modules.classifier_v0 import classifier_v0
        return classifier_v0
    if settings.classifier_version == "v1":
        from agents.triage.dspy_modules.classifier_v1 import classifier_v1
        return classifier_v1
    elif settings.classifier_version == "v2":
        from agents.triage.dspy_modules.classifier_v2.classifier_v2 import classifier_v2
        return classifier_v2
    elif settings.classifier_version == "v3":
        from agents.triage.baseline_model.classifier_v3 import classifier_v3
        return classifier_v3
    elif settings.classifier_version == "v4":
        from agents.triage.dspy_modules.classifier_v4 import classifier_v4
        return classifier_v4
    else:
        raise ValueError(f"Unknown classifier version: {settings.classifier_version}")


current_classifier = get_current_classifier()


@triage_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda msg: msg.get("type") == "user_message",
    auto_offset_reset="latest",
    group_id="triage_agent_group"
)
@traced_handler("handle_user_message")
async def handle_user_message(msg: TracedMessage):
    try:
        chat_messages = msg.data.get("chat_messages", [])
        connection_id = msg.data.get("connection_id", "unknown")

        logger.info(f"Received message from connection {connection_id}")
        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        response = current_classifier(chat_history=conversation_string)
        target_agent = response.target_agent

        logger.info(
            f"Classification completed in {response.metrics.latency_ms:.2f} ms, target agent: {target_agent}, classifier version: {settings.classifier_version}")
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        if target_agent != TargetAgent.ChattyAgent:
            logger.info(f"Routing message to {target_agent}")

            with tracer.start_as_current_span("publish_to_agent") as publish_span:
                child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
                await agents_channel.publish(
                    TracedMessage(
                        type=AGENT_REGISTRY[target_agent]["message_type"],
                        source="TriageAgent",
                        data={
                            "chat_messages": triage_to_agent_messages,
                            "message_id": msg.id,
                            "connection_id": connection_id,
                            "metrics": response.metrics,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
        else:
            # Use streaming implementation for chatty responses
            with tracer.start_as_current_span("chatty_stream_response") as stream_span:
                child_traceparent, child_tracestate = format_span_as_traceparent(stream_span)

                stream_message_id = str(msg.id) # Use the same message ID for the stream

                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_start",
                        source="TriageAgent",
                        data={
                            "message_id": stream_message_id,
                            "connection_id": connection_id,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )

                chunks = chatty(chat_history=conversation_string)
                chunk_count = 0

                async for chunk in chunks:
                    if isinstance(chunk, dspy.streaming.StreamResponse):
                        chunk_count += 1
                        await human_stream_channel.publish(TracedMessage(
                            type="agent_message_stream_chunk",
                            source="TriageAgent",
                            data={
                                "message_chunk": chunk.chunk,
                                "message_id": stream_message_id,
                                "chunk_index": chunk_count,
                                "connection_id": connection_id,
                            },
                            traceparent=child_traceparent,
                            tracestate=child_tracestate,
                        ))
                        logger.info(f"Chunk {chunk_count} sent: {chunk.chunk}")
                    elif isinstance(chunk, dspy.Prediction):
                        # FIXME: with short prompts, sometime dspy is not trimming off the " [[ ## completed ## ]]", we will do it manually there
                        chunk.response = chunk.response.replace(" [[ ## completed ## ]]", "")

                        await human_stream_channel.publish(
                            TracedMessage(
                                type="agent_message_stream_end",
                                source="TriageAgent",
                                data={
                                    "message_id": stream_message_id,
                                    "agent": "TriageAgent",
                                    "connection_id": connection_id,
                                    "metrics": response.metrics,
                                    "message": chunk.response,
                                },
                                traceparent=child_traceparent,
                                tracestate=child_tracestate,
                            )
                        )
                        logger.info(f"Stream ended for message {stream_message_id}: {chunk.response}")

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
                print(chunk.chunk, end='')
            elif isinstance(chunk, dspy.Prediction):
                print("")
                print(chunk.get_lm_usage())
    asyncio.run(run())
