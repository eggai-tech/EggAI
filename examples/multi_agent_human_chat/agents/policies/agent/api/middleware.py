import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from libraries.observability.logger import get_console_logger

logger = get_console_logger("policies_api_middleware")


async def add_process_time_header(request: Request, call_next: Callable) -> Response:
    """Add X-Process-Time header to track request processing time.
    
    Args:
        request: The incoming request
        call_next: The next middleware or endpoint
        
    Returns:
        Response with added header
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


async def catch_exceptions_middleware(request: Request, call_next: Callable) -> Response:
    """Catch unhandled exceptions and return proper error responses.
    
    Args:
        request: The incoming request
        call_next: The next middleware or endpoint
        
    Returns:
        Response or error response
    """
    try:
        return await call_next(request)
    except Exception as e:
        # Log the error with full traceback
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        
        # Return generic error response to avoid exposing internals
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again later."}
        )


async def add_security_headers(request: Request, call_next: Callable) -> Response:
    """Add security headers to responses.
    
    Args:
        request: The incoming request
        call_next: The next middleware or endpoint
        
    Returns:
        Response with security headers
    """
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response