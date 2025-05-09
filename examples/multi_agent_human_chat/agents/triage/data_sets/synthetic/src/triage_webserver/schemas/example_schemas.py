from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ExampleBase(BaseModel):
    conversation: str
    target_agent: str
    turns: int
    temperature: float
    special_case: Optional[str] = None

class ExampleCreate(ExampleBase):
    dataset_id: int
    index_batch: Optional[int] = None
    total_batch: Optional[int] = None

class ExampleUpdate(BaseModel):
    conversation: Optional[str] = None
    target_agent: Optional[str] = None
    turns: Optional[int] = None
    temperature: Optional[float] = None
    special_case: Optional[str] = None

class ExampleResponse(ExampleBase):
    id: int
    dataset_id: int
    index_batch: Optional[int]
    total_batch: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True
    }

class ExampleList(BaseModel):
    examples: List[ExampleResponse]
    total: int