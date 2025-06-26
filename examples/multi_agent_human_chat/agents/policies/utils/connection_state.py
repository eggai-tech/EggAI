"""Connection state management utilities."""


def set_current_connection_id(conn_id: str) -> None:
    """Set the current connection ID in global state."""
    globals()["current_connection_id"] = conn_id


def get_current_connection_id() -> str:
    """Get the current connection ID from global state."""
    return globals().get("current_connection_id", None)
