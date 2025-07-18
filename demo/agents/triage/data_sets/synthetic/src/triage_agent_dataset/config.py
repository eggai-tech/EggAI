from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    TOTAL_TARGET: int = 100
    AGENT_DISTRIBUTION: dict = {
        "BillingAgent": 0.3,
        "PolicyAgent": 0.2,
        "ClaimsAgent": 0.25,
        "EscalationAgent": 0.15,
        "ChattyAgent": 0.1,
    }
    SPECIAL_CASE_DISTRIBUTION: dict = {
        "none": 0.5,
        "edge_case": 0.1,
        "cross_domain": 0.1,
        "language_switch": 0.1,
        "short_query": 0.05,
        "complex_query": 0.05,
        "small_talk": 0.05,
        "angry_customer": 0.025,
        "technical_error": 0.025,
    }
    MODEL: str = "openai/gpt-4o-mini"

    class Config:
        env_prefix = ""
