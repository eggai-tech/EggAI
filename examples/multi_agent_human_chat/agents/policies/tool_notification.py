from eggai import Channel

from agents.policies.dspy_modules.current_state import get_current_connection_id
from libraries.channels import channels
from libraries.tracing import TracedMessage

human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human + "_stream")


async def send_tool_usage_notification(message: str) -> None:
    await human_stream_channel.publish(
        TracedMessage(
            type="agent_message_stream_waiting_message",
            source="PoliciesAgent",
            data={
                "message": message,
                "connection_id": get_current_connection_id(),
            },
        )
    )
