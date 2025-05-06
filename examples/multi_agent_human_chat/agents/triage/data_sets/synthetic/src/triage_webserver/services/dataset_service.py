import asyncio
from typing import List, Dict, Any, Optional
import datetime

from sqlalchemy.orm import Session
from tqdm import tqdm

from triage_agent_dataset.models import Agents, SpecialCaseType
from triage_agent_dataset.dataset_generator import generate_conversation_per_agent
from triage_webserver.models.data_models import Dataset, Example
from triage_webserver.config import WebServerConfig

config = WebServerConfig()

async def create_dataset(
    db: Session,
    name: str,
    description: Optional[str] = None,
    total_target: int = 100,
    agent_distribution: Optional[Dict[str, float]] = None,
    special_case_distribution: Optional[Dict[str, float]] = None,
    temperatures: List[float] = [0.7, 0.8, 0.9],
    turns: List[int] = [1, 3, 5],
    model: Optional[str] = None
) -> Dataset:
    """
    Create a new dataset with generated examples using the dataset generator
    """
    if agent_distribution is None:
        agent_distribution = {
            "BillingAgent": 0.3,
            "PolicyAgent": 0.2,
            "ClaimsAgent": 0.25,
            "EscalationAgent": 0.15,
            "ChattyAgent": 0.1,
        }
    
    if special_case_distribution is None:
        special_case_distribution = {
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
    
    if model is None:
        model = config.MODEL
    
    # Create the dataset in the database
    dataset = Dataset(
        name=name,
        description=description,
        model=model,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    
    # Calculate total examples for progress tracking
    total_examples = 0
    for agent in Agents:
        agent_frac = agent_distribution.get(agent.value, 0)
        agent_target = max(round(total_target * agent_frac), 1)
        num_combinations = len(turns) * len(temperatures)
        ideal_per_combo = agent_target / num_combinations
        for _ in range(len(turns) * len(temperatures)):
            for frac in special_case_distribution.values():
                count = round(ideal_per_combo * frac)
                total_examples += max(count, 1)
    
    # Set up progress tracking
    progress = tqdm(total=total_examples, desc=f"Generating Dataset: {name}")
    
    # Generate examples for each agent
    agent_tasks = [
        generate_conversation_per_agent(agent, turns, temperatures, progress)
        for agent in Agents
    ]
    results = await asyncio.gather(*agent_tasks)
    progress.close()
    
    # Flatten results
    examples = []
    for agent_result in results:
        examples.extend(agent_result)
    
    # Save examples to database
    for example_data in examples:
        example = Example(
            dataset_id=dataset.id,
            conversation=example_data.conversation,
            target_agent=example_data.target_agent,
            turns=example_data.turns,
            temperature=example_data.temperature,
            index_batch=example_data.index_batch,
            total_batch=example_data.total_batch,
            special_case=example_data.special_case,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db.add(example)
    
    # Update dataset with final count
    dataset.total_examples = len(examples)
    db.commit()
    db.refresh(dataset)
    
    return dataset

def get_dataset(db: Session, dataset_id: int) -> Optional[Dataset]:
    """
    Get a dataset by ID
    """
    return db.query(Dataset).filter(Dataset.id == dataset_id).first()

def get_datasets(db: Session, skip: int = 0, limit: int = 100) -> List[Dataset]:
    """
    Get all datasets
    """
    return db.query(Dataset).offset(skip).limit(limit).all()

def delete_dataset(db: Session, dataset_id: int) -> bool:
    """
    Delete a dataset and all its examples
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset:
        db.delete(dataset)
        db.commit()
        return True
    return False