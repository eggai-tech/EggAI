from faststream.kafka import KafkaMessage
from eggai import Channel, Agent
from eggai.transport import KafkaTransport, eggai_set_default_transport
from libraries.logger import get_console_logger
from .config import settings

eggai_set_default_transport(lambda: KafkaTransport(bootstrap_servers=settings.kafka_bootstrap_servers))

agents_channel = Channel("agents")
human_channel = Channel("human")

logger = get_console_logger("audit_agent")


audit_agent = Agent("AuditAgent")

@audit_agent.subscribe(pattern="{channel}")
def audit_message(message, msg: KafkaMessage):
    logger.info(f"AuditAgent received message: channel={msg.path}, {message}")
    return message