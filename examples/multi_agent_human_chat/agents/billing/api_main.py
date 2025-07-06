"""
Billing Agent API for Admin UI
Provides REST endpoints for billing management and monitoring
"""
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.billing.dspy_modules.billing_data import BILLING_DATABASE
from libraries.logger import get_console_logger

logger = get_console_logger("billing_api")

app = FastAPI(
    title="Billing Agent API",
    description="API for managing and monitoring billing records",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BillingRecord(BaseModel):
    """Billing record model"""
    policy_number: str
    customer_name: str
    amount_due: float
    due_date: str
    status: str
    billing_cycle: str
    last_payment_date: Optional[str] = None
    last_payment_amount: Optional[float] = None


class BillingListResponse(BaseModel):
    """Response model for billing list"""
    records: List[BillingRecord]
    total: int
    total_due: float
    total_paid: float
    by_status: dict


class BillingStats(BaseModel):
    """Statistics about billing"""
    total_records: int
    total_amount_due: float
    total_amount_paid: float
    overdue_count: int
    by_status: dict
    by_cycle: dict
    average_amount: float


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "billing-agent-api", "version": "1.0.0"}


@app.get("/api/v1/billing", response_model=BillingListResponse)
async def list_billing_records(
    status: Optional[str] = Query(None, description="Filter by status (Paid/Pending)"),
    billing_cycle: Optional[str] = Query(None, description="Filter by billing cycle"),
    policy_number: Optional[str] = Query(None, description="Filter by policy number"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all billing records with optional filtering"""
    try:
        # Filter records (BILLING_DATABASE is already a list)
        filtered_records = BILLING_DATABASE.copy()
        
        if status:
            filtered_records = [r for r in filtered_records if r["status"].lower() == status.lower()]
        
        if billing_cycle:
            filtered_records = [r for r in filtered_records if r["billing_cycle"].lower() == billing_cycle.lower()]
            
        if policy_number:
            filtered_records = [r for r in filtered_records if r["policy_number"] == policy_number]
        
        # Calculate totals
        total_due = sum(r["amount_due"] for r in filtered_records if r["status"] == "Pending")
        total_paid = sum(r.get("last_payment_amount", 0) for r in filtered_records if r["status"] == "Paid")
        
        by_status = {}
        for record in filtered_records:
            by_status[record["status"]] = by_status.get(record["status"], 0) + 1
        
        # Apply pagination
        paginated_records = filtered_records[offset:offset + limit]
        
        # Convert to response models
        billing_records = [BillingRecord(**record) for record in paginated_records]
        
        return BillingListResponse(
            records=billing_records,
            total=len(filtered_records),
            total_due=total_due,
            total_paid=total_paid,
            by_status=by_status
        )
    except Exception as e:
        logger.error(f"Error listing billing records: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/billing/stats", response_model=BillingStats)
async def get_billing_statistics():
    """Get statistics about all billing records"""
    try:
        from datetime import datetime
        
        total_due = 0
        total_paid = 0
        overdue_count = 0
        by_status = {}
        by_cycle = {}
        
        today = datetime.now().date()
        
        for record in BILLING_DATABASE:
            # Status counts
            by_status[record["status"]] = by_status.get(record["status"], 0) + 1
            
            # Cycle counts
            by_cycle[record["billing_cycle"]] = by_cycle.get(record["billing_cycle"], 0) + 1
            
            # Calculate totals
            if record["status"] == "Pending":
                total_due += record["amount_due"]
                # Check if overdue
                due_date = datetime.strptime(record["due_date"], "%Y-%m-%d").date()
                if due_date < today:
                    overdue_count += 1
            else:
                total_paid += record.get("last_payment_amount", 0)
        
        total_amount = sum(r["amount_due"] for r in BILLING_DATABASE)
        avg_amount = total_amount / len(BILLING_DATABASE) if BILLING_DATABASE else 0
        
        return BillingStats(
            total_records=len(BILLING_DATABASE),
            total_amount_due=total_due,
            total_amount_paid=total_paid,
            overdue_count=overdue_count,
            by_status=by_status,
            by_cycle=by_cycle,
            average_amount=avg_amount
        )
    except Exception as e:
        logger.error(f"Error calculating statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/billing/{policy_number}", response_model=BillingRecord)
async def get_billing_record(policy_number: str):
    """Get billing information for a specific policy"""
    try:
        # Find the record in the list
        record = None
        for billing_record in BILLING_DATABASE:
            if billing_record["policy_number"] == policy_number:
                record = billing_record
                break
        
        if not record:
            raise HTTPException(status_code=404, detail=f"Billing record not found: {policy_number}")
        
        return BillingRecord(**record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting billing record: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agents.billing.api_main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info",
    )