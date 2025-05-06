from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from triage_webserver.database.connection import get_db
from triage_webserver.models.data_models import Dataset
from triage_webserver.services.dataset_service import (
    create_dataset, get_dataset, get_datasets, delete_dataset
)
from triage_webserver.schemas.dataset_schemas import (
    DatasetCreate, DatasetResponse, DatasetList
)

router = APIRouter()

@router.post("/", response_model=DatasetResponse)
async def create_new_dataset(
    dataset_data: DatasetCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new dataset with specified parameters
    """
    # Start dataset generation in background
    background_tasks.add_task(
        create_dataset,
        db=db,
        name=dataset_data.name,
        description=dataset_data.description,
        total_target=dataset_data.total_target,
        agent_distribution=dataset_data.agent_distribution,
        special_case_distribution=dataset_data.special_case_distribution,
        temperatures=dataset_data.temperatures,
        turns=dataset_data.turns,
        model=dataset_data.model
    )
    
    return JSONResponse(
        status_code=202,
        content={"message": f"Dataset '{dataset_data.name}' generation started"}
    )

@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset_by_id(dataset_id: int, db: Session = Depends(get_db)):
    """
    Get a dataset by ID
    """
    db_dataset = get_dataset(db, dataset_id)
    if db_dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return db_dataset

@router.get("/", response_model=DatasetList)
def get_all_datasets(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Get all datasets
    """
    datasets = get_datasets(db, skip=skip, limit=limit)
    return {"datasets": datasets, "total": len(datasets)}

@router.delete("/{dataset_id}")
def delete_dataset_by_id(dataset_id: int, db: Session = Depends(get_db)):
    """
    Delete a dataset by ID
    """
    result = delete_dataset(db, dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"message": "Dataset deleted successfully"}