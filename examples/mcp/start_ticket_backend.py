from enum import Enum

from fastmcp import FastMCP
import dotenv
from pydantic import BaseModel

dotenv.load_dotenv()
mcp = FastMCP("SupportTicketSystem", version="1.0.0", host="localhost", port=8000, sse_path="/sse")

class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class Ticket(BaseModel):
    id: int
    description: str
    status: TicketStatus

_TICKETS = [Ticket(id=1, description="Initial ticket", status=TicketStatus.OPEN)]

@mcp.tool
def create_ticket(title: str) -> Ticket:
    """Create a new support ticket."""
    ticket_id = len(_TICKETS) + 1
    new_ticket = Ticket(id=ticket_id, description=title, status=TicketStatus.OPEN)
    _TICKETS.append(new_ticket)
    return new_ticket

@mcp.tool
def list_tickets() -> list[Ticket]:
    """List all support tickets."""
    return _TICKETS

@mcp.tool
def update_ticket(ticket_id: int, status: TicketStatus) -> Ticket:
    """Update the status of a support ticket."""
    for ticket in _TICKETS:
        if ticket.id == ticket_id:
            ticket.status = status
            return ticket
    raise ValueError(f"Ticket with ID {ticket_id} not found.")

@mcp.tool
def delete_ticket(ticket_id: int) -> str:
    """Delete a support ticket."""
    global _TICKETS
    _TICKETS = [ticket for ticket in _TICKETS if ticket.id != ticket_id]
    return f"Ticket with ID {ticket_id} has been deleted."


if __name__ == "__main__":
    try:
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        print("MCP server stopped.")