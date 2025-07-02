"""Routes for the Policies Agent API."""

from libraries.vespa import VespaClient

vespa_client = VespaClient()

__all__ = ["vespa_client"]
