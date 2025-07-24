from enum import Enum

from openai import BaseModel


class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Ticket(BaseModel):
    id: int
    description: str
    status: TicketStatus


TICKET_ADAPTER_NAME = "SupportTicketSystemAdapter"