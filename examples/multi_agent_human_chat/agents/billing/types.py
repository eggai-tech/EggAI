from typing import Optional

from pydantic import BaseModel, Field

from libraries.types import ChatMessage as ChatMessage
from libraries.types import ModelConfig as BaseModelConfig
from libraries.types import ModelResult as ModelResult


class BillingModelConfig(BaseModelConfig):
    name: str = Field(default="billing_react", description="Name of the model")

class BillingRecord(BaseModel):

    policy_number: str = Field(..., description="Unique identifier for the policy")
    customer_name: str = Field(..., description="Name of the customer")
    amount_due: float = Field(..., description="Amount due", ge=0)
    due_date: str = Field(..., description="Due date for payment (YYYY-MM-DD)")
    billing_status: str = Field(..., description="Current billing status")
    billing_cycle: str = Field(
        ..., description="Billing cycle (monthly, quarterly, etc.)"
    )
    last_payment_date: Optional[str] = Field(
        None, description="Date of last payment (YYYY-MM-DD)"
    )
    last_payment_amount: Optional[float] = Field(
        None, description="Amount of last payment", ge=0
    )
    next_payment_amount: Optional[float] = Field(
        None, description="Amount of next payment", ge=0
    )
    contact_email: Optional[str] = Field(None, description="Contact email address")
    contact_phone: Optional[str] = Field(None, description="Contact phone number")

    model_config = {"extra": "forbid"}

ModelConfig = BillingModelConfig


