import ssl
from aiokafka.helpers import create_ssl_context

def create_ssl_context_from_settings(ca_content: str) -> ssl.SSLContext:
    context = create_ssl_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    context.load_verify_locations(cadata=ca_content)
    return context