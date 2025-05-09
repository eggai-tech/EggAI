from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class DatasetBase(BaseModel):
    name: str
    description: Optional[str] = None
    model: Optional[str] = None

class DatasetCreate(DatasetBase):
    total_target: int = 100
    agent_distribution: Optional[Dict[str, float]] = None
    special_case_distribution: Optional[Dict[str, float]] = None
    temperatures: List[float] = [0.7, 0.8, 0.9]
    turns: List[int] = [1, 3, 5]

class DatasetResponse(DatasetBase):
    id: int
    total_examples: int
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True
    }

class DatasetList(BaseModel):
    datasets: List[DatasetResponse]
    total: int