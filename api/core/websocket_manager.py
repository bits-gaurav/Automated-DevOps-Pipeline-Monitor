from fastapi import WebSocket
from typing import List, Dict, Set
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, events: List[str]):
        """Subscribe a WebSocket to specific events"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].update(events)
            await websocket.send_text(json.dumps({
                "type": "subscription_confirmed",
                "events": list(self.subscriptions[websocket])
            }))
    
    async def broadcast(self, message: dict, event_type: str = None):
        """Broadcast a message to all connected clients or specific subscribers"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = []
        
        for websocket in self.active_connections:
            try:
                # If event_type is specified, only send to subscribers
                if event_type and websocket in self.subscriptions:
                    if event_type not in self.subscriptions[websocket]:
                        continue
                
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def send_pipeline_update(self, pipeline_data: dict):
        """Send pipeline status update"""
        await self.broadcast({
            "type": "pipeline_update",
            "data": pipeline_data,
            "timestamp": pipeline_data.get("timestamp")
        }, "pipeline")
    
    async def send_build_update(self, build_data: dict):
        """Send build status update"""
        await self.broadcast({
            "type": "build_update",
            "data": build_data,
            "timestamp": build_data.get("timestamp")
        }, "builds")
    
    async def send_analytics_update(self, analytics_data: dict):
        """Send analytics update"""
        await self.broadcast({
            "type": "analytics_update",
            "data": analytics_data,
            "timestamp": analytics_data.get("timestamp")
        }, "analytics")
    
    async def send_notification_update(self, notification_data: dict):
        """Send notification update"""
        await self.broadcast({
            "type": "notification_update",
            "data": notification_data,
            "timestamp": notification_data.get("timestamp")
        }, "notifications")
