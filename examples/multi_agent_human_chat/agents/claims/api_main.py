"""
Claims Agent API for Admin UI
Provides REST endpoints for claims management and monitoring
"""
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.claims.dspy_modules.claims_data import (
    CLAIMS_DATABASE,
    get_claim_record,
)
from agents.claims.types import ClaimRecord
from libraries.logger import get_console_logger

logger = get_console_logger("claims_api")

app = FastAPI(
    title="Claims Agent API",
    description="API for managing and monitoring insurance claims",
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


class ClaimSummary(BaseModel):
    """Summary model for claim listings"""
    claim_number: str
    policy_number: str
    status: str
    estimate: Optional[float] = None
    estimate_date: Optional[str] = None
    next_steps: str
    outstanding_items: List[str] = []


class ClaimsListResponse(BaseModel):
    """Response model for claims list"""
    claims: List[ClaimSummary]
    total: int
    by_status: dict


class ClaimStats(BaseModel):
    """Statistics about claims"""
    total_claims: int
    total_estimated: float
    by_status: dict
    by_policy: dict
    average_estimate: Optional[float]


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "claims-agent-api", "version": "1.0.0"}


@app.get("/api/v1/claims", response_model=ClaimsListResponse)
async def list_claims(
    status: Optional[str] = Query(None, description="Filter by status"),
    policy_number: Optional[str] = Query(None, description="Filter by policy number"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all claims with optional filtering"""
    try:
        # Filter claims
        filtered_claims = CLAIMS_DATABASE
        
        if status:
            filtered_claims = [c for c in filtered_claims if c.status.lower() == status.lower()]
        
        if policy_number:
            filtered_claims = [c for c in filtered_claims if c.policy_number == policy_number]
        
        # Calculate statistics
        by_status = {}
        for claim in filtered_claims:
            by_status[claim.status] = by_status.get(claim.status, 0) + 1
        
        # Apply pagination
        paginated_claims = filtered_claims[offset:offset + limit]
        
        # Convert to summary format
        claim_summaries = [
            ClaimSummary(
                claim_number=claim.claim_number,
                policy_number=claim.policy_number,
                status=claim.status,
                estimate=claim.estimate,
                estimate_date=claim.estimate_date,
                next_steps=claim.next_steps,
                outstanding_items=claim.outstanding_items,
            )
            for claim in paginated_claims
        ]
        
        return ClaimsListResponse(
            claims=claim_summaries,
            total=len(filtered_claims),
            by_status=by_status
        )
    except Exception as e:
        logger.error(f"Error listing claims: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/claims/stats", response_model=ClaimStats)
async def get_claims_statistics():
    """Get statistics about all claims"""
    try:
        total_estimated = 0
        count_with_estimate = 0
        by_status = {}
        by_policy = {}
        
        for claim in CLAIMS_DATABASE:
            # Status counts
            by_status[claim.status] = by_status.get(claim.status, 0) + 1
            
            # Policy counts
            by_policy[claim.policy_number] = by_policy.get(claim.policy_number, 0) + 1
            
            # Sum estimates
            if claim.estimate:
                total_estimated += claim.estimate
                count_with_estimate += 1
        
        avg_estimate = total_estimated / count_with_estimate if count_with_estimate > 0 else None
        
        return ClaimStats(
            total_claims=len(CLAIMS_DATABASE),
            total_estimated=total_estimated,
            by_status=by_status,
            by_policy=by_policy,
            average_estimate=avg_estimate
        )
    except Exception as e:
        logger.error(f"Error calculating statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/claims/{claim_number}", response_model=ClaimRecord)
async def get_claim(claim_number: str):
    """Get detailed information about a specific claim"""
    try:
        claim = get_claim_record(claim_number)
        if not claim:
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_number}")
        return claim
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting claim: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agents.claims.api_main:app",
        host="0.0.0.0",
        port=8003,
        reload=False,
        log_level="info",
    )