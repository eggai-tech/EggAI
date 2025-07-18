import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from triage_webserver.database.connection import get_db, init_db
from triage_webserver.models.data_models import Dataset, Example
from triage_webserver.routes import datasets, examples

app = FastAPI(title="Triage Dataset Manager")

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=templates_path)

app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(examples.router, prefix="/api/examples", tags=["examples"])


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        init_db()
    except Exception as e:
        print(f"\n{'=' * 80}\nDATABASE ERROR: {str(e)}")
        print("Make sure your database is running and your DATABASE_URL is correct.")
        print("For Docker, run: docker-compose up -d db")
        print("For local development, make sure PostgreSQL is running.")
        print(f"{'=' * 80}\n")
        # Still raise the error so the app won't start with a broken database
        raise


# Helper function for formatting dates in templates
def format_date(date_string):
    from datetime import datetime

    date = datetime.fromisoformat(str(date_string).replace("Z", "+00:00"))
    return date.strftime("%b %d, %Y")


# Add template filters
templates.env.filters["format_date"] = format_date


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Render the homepage with datasets list"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/datasets/create", response_class=HTMLResponse)
async def create_dataset_page(request: Request):
    """Render the create dataset page"""
    return templates.TemplateResponse("create_dataset.html", {"request": request})


@app.get("/datasets/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail(
    request: Request, dataset_id: int, db: Session = Depends(get_db)
):
    """Render the dataset detail page"""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return templates.TemplateResponse(
        "dataset_detail.html",
        {"request": request, "dataset": dataset, "format_date": format_date},
    )


@app.get("/examples/{example_id}/edit", response_class=HTMLResponse)
async def edit_example(
    request: Request, example_id: int, db: Session = Depends(get_db)
):
    """Render the edit example page"""
    from json import dumps

    example = db.query(Example).filter(Example.id == example_id).first()
    if not example:
        raise HTTPException(status_code=404, detail="Example not found")

    dataset = db.query(Dataset).filter(Dataset.id == example.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Convert example to JSON for Alpine.js
    example_dict = {
        "id": example.id,
        "dataset_id": example.dataset_id,
        "conversation": example.conversation,
        "target_agent": example.target_agent,
        "turns": example.turns,
        "temperature": example.temperature,
        "special_case": example.special_case,
        "index_batch": example.index_batch,
        "total_batch": example.total_batch,
    }
    example_json = dumps(example_dict)

    return templates.TemplateResponse(
        "edit_example.html",
        {
            "request": request,
            "example": example,
            "example_json": example_json,
            "dataset": dataset,
            "format_date": format_date,
        },
    )


@app.get("/docs", include_in_schema=False)
async def docs_redirect():
    """Redirect /docs to the API documentation"""
    return RedirectResponse(url="/docs")
