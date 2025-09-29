from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from typing import List
import json
from datetime import datetime, timezone

from routers import pipeline, builds, analytics, notifications
from core.websocket_manager import WebSocketManager
from core.config import settings
from core.exceptions import (
    APIException,
    GitHubAPIException,
    SlackAPIException,
    ValidationException,
    NotFoundError,
    RateLimitException,
    api_exception_handler,
    validation_exception_handler,
    general_exception_handler,
    http_exception_handler_custom
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket manager instance
websocket_manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting DevOps Pipeline API service...")
    yield
    logger.info("Shutting down DevOps Pipeline API service...")

# Create FastAPI app
app = FastAPI(
    title="DevOps Pipeline Monitor API",
    description="Comprehensive API service for monitoring CI/CD pipelines, builds, and analytics",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(GitHubAPIException, api_exception_handler)
app.add_exception_handler(SlackAPIException, api_exception_handler)
app.add_exception_handler(ValidationException, api_exception_handler)
app.add_exception_handler(NotFoundError, api_exception_handler)
app.add_exception_handler(RateLimitException, api_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler_custom)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Pipeline"])
app.include_router(builds.router, prefix="/api/v1/builds", tags=["Builds"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DevOps Pipeline Monitor API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "devops-pipeline-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "subscribe":
                # Subscribe to specific events
                await websocket_manager.subscribe(websocket, message.get("events", []))
            elif message.get("type") == "ping":
                # Respond to ping with pong
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket)

# Make websocket_manager available to other modules
app.state.websocket_manager = websocket_manager

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
