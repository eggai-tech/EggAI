"""A2A configuration for EggAI agents."""

from pydantic import BaseModel, ConfigDict, Field

try:
    from a2a.types import SecurityScheme
except ImportError:
    # Fallback if a2a-sdk not installed
    SecurityScheme = dict


class A2AConfig(BaseModel):
    """Simple A2A configuration for EggAI agents."""

    agent_name: str = Field(..., description="Name of the A2A agent")
    description: str = Field(..., description="Description of what the agent does")
    version: str = Field(default="1.0.0", description="Agent version")
    base_url: str = Field(
        default="http://localhost:8080", description="Base URL for the A2A server"
    )
    security_schemes: list[SecurityScheme] | None = Field(
        default=None, description="Security schemes supported by the agent"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
