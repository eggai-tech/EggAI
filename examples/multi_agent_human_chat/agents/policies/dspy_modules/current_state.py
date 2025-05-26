def set_current_connection_id(conn_id: str):
    globals()["current_connection_id"] = conn_id

def get_current_connection_id():
    return globals().get("current_connection_id", None)