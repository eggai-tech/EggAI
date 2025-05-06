from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String
from typing import List, Optional, Union

from triage_webserver.database.connection import get_db
from triage_webserver.models.data_models import Example
from triage_webserver.schemas.example_schemas import ExampleResponse, ExampleUpdate, ExampleList

router = APIRouter()

@router.get("/{example_id}", response_model=ExampleResponse)
def get_example(example_id: int, db: Session = Depends(get_db)):
    """
    Get a single example by ID
    """
    example = db.query(Example).filter(Example.id == example_id).first()
    if example is None:
        raise HTTPException(status_code=404, detail="Example not found")
    return example

@router.get("/", response_model=ExampleList)
def get_examples(
    dataset_id: Optional[int] = None,
    target_agent: Optional[str] = None,
    special_case: Optional[Union[str, None]] = None,
    turns: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get examples with optional filtering
    
    - dataset_id: Filter by dataset ID
    - target_agent: Filter by target agent
    - special_case: Filter by special case (use "null" for examples with no special case)
    - turns: Filter by number of turns
    - search: Search in conversation text
    - skip: Number of examples to skip (for pagination)
    - limit: Maximum number of examples to return
    """
    query = db.query(Example)
    
    # Apply filters
    if dataset_id is not None:
        query = query.filter(Example.dataset_id == dataset_id)
    
    if target_agent is not None:
        query = query.filter(Example.target_agent == target_agent)
    
    if special_case is not None:
        if special_case.lower() == "null":
            query = query.filter(Example.special_case.is_(None))
        else:
            query = query.filter(Example.special_case == special_case)
    
    if turns is not None:
        query = query.filter(Example.turns == turns)
    
    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(Example.conversation.ilike(search_pattern))
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    examples = query.order_by(Example.id.desc()).offset(skip).limit(limit).all()
    
    return {"examples": examples, "total": total}

@router.put("/{example_id}", response_model=ExampleResponse)
def update_example(
    example_id: int, 
    example_data: ExampleUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update an example
    """
    example = db.query(Example).filter(Example.id == example_id).first()
    if example is None:
        raise HTTPException(status_code=404, detail="Example not found")
    
    # Update fields
    for field, value in example_data.model_dump(exclude_unset=True).items():
        setattr(example, field, value)
    
    db.commit()
    db.refresh(example)
    return example

@router.delete("/{example_id}")
def delete_example(example_id: int, db: Session = Depends(get_db)):
    """
    Delete an example
    """
    example = db.query(Example).filter(Example.id == example_id).first()
    if example is None:
        raise HTTPException(status_code=404, detail="Example not found")
    
    db.delete(example)
    db.commit()
    
    return {"message": "Example deleted successfully"}