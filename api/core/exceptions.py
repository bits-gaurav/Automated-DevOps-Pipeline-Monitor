from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
import logging
from typing import Union

logger = logging.getLogger(__name__)

class APIException(Exception):
    """Base API exception"""
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class GitHubAPIException(APIException):
    """GitHub API related exception"""
    def __init__(self, message: str, status_code: int = 502, details: dict = None):
        super().__init__(message, status_code, details)

class SlackAPIException(APIException):
    """Slack API related exception"""
    def __init__(self, message: str, status_code: int = 502, details: dict = None):
        super().__init__(message, status_code, details)

class ValidationException(APIException):
    """Validation related exception"""
    def __init__(self, message: str, status_code: int = 400, details: dict = None):
        super().__init__(message, status_code, details)

class NotFoundError(APIException):
    """Resource not found exception"""
    def __init__(self, resource: str, identifier: Union[str, int]):
        message = f"{resource} with identifier '{identifier}' not found"
        super().__init__(message, 404, {"resource": resource, "identifier": str(identifier)})

class RateLimitException(APIException):
    """Rate limit exceeded exception"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, 429, details)

async def api_exception_handler(request: Request, exc: APIException):
    """Handle custom API exceptions"""
    logger.error(f"API Exception: {exc.message}", extra={
        "status_code": exc.status_code,
        "details": exc.details,
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": exc.__class__.__name__,
                "details": exc.details,
                "timestamp": "2025-09-29T11:27:51+05:30",
                "path": request.url.path
            }
        }
    )

async def validation_exception_handler(request: Request, exc: Exception):
    """Handle validation exceptions"""
    logger.error(f"Validation error: {str(exc)}", extra={
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Validation error",
                "type": "ValidationError",
                "details": {"validation_error": str(exc)},
                "timestamp": "2025-09-29T11:27:51+05:30",
                "path": request.url.path
            }
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", extra={
        "path": request.url.path,
        "method": request.method,
        "exception_type": exc.__class__.__name__
    }, exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "InternalServerError",
                "details": {"error_id": f"err_{hash(str(exc)) % 10000:04d}"},
                "timestamp": "2025-09-29T11:27:51+05:30",
                "path": request.url.path
            }
        }
    )

async def http_exception_handler_custom(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    logger.warning(f"HTTP Exception: {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "HTTPException",
                "details": {},
                "timestamp": "2025-09-29T11:27:51+05:30",
                "path": request.url.path
            }
        }
    )
