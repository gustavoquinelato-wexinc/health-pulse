"""
WebSocket Manager for Real-time Progress and Exception Tracking

Handles WebSocket connections for live job progress updates and exception logging.
Replaces database-based progress tracking with real-time event streaming.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.core.logging_config import get_logger
from datetime import datetime
from enum import Enum

logger = get_logger(__name__)


class MessageType(Enum):
    """WebSocket message types for different kinds of updates."""
    PROGRESS = "progress"
    EXCEPTION = "exception"
    STATUS = "status"
    COMPLETION = "completion"


class WebSocketManager:
    """
    Manages WebSocket connections for real-time job monitoring.
    
    Features:
    - Real-time progress updates
    - Exception-only logging
    - Multiple client support
    - Automatic cleanup
    """
    
    def __init__(self):
        # Store active connections by job name
        self.connections: Dict[str, List[WebSocket]] = {}
        # Store latest progress for new connections
        self.latest_progress: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, job_name: str):
        """Accept a new WebSocket connection for a specific job."""
        await websocket.accept()
        
        if job_name not in self.connections:
            self.connections[job_name] = []
        
        self.connections[job_name].append(websocket)
        logger.info("[WS] Connected", job_name=job_name, total_connections=len(self.connections[job_name]))
        
        # Send latest progress if available
        if job_name in self.latest_progress:
            try:
                await websocket.send_text(json.dumps(self.latest_progress[job_name]))
            except Exception as e:
                logger.warning("[WS] Failed to send latest progress to new connection", error=str(e))
    
    def disconnect(self, websocket: WebSocket, job_name: str):
        """Remove a WebSocket connection."""
        if job_name in self.connections:
            try:
                self.connections[job_name].remove(websocket)
                logger.info("[WS] Disconnected", job_name=job_name, remaining_connections=len(self.connections[job_name]))
                
                # Clean up empty job lists
                if not self.connections[job_name]:
                    del self.connections[job_name]
                    
            except ValueError:
                logger.warning("[WS] WebSocket not found in connections", job_name=job_name)
    
    async def send_progress_update(self, job_name: str, percentage: Optional[float], step: str):
        """Send progress update to all connected clients for a job."""
        message = {
            "type": MessageType.PROGRESS.value,
            "job": job_name,
            "percentage": round(percentage, 1) if percentage is not None else None,
            "step": step,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store latest progress for new connections
        self.latest_progress[job_name] = message
        
        await self._broadcast_to_job(job_name, message)
    
    async def send_exception(self, job_name: str, level: str, message: str, error_details: Optional[str] = None):
        """Send exception/error message to all connected clients for a job."""
        exception_message = {
            "type": MessageType.EXCEPTION.value,
            "job": job_name,
            "level": level.upper(),  # ERROR, WARNING, INFO
            "message": message,
            "details": error_details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcast_to_job(job_name, exception_message)
    
    async def send_status_update(self, job_name: str, status: str, details: Optional[Dict[str, Any]] = None):
        """Send job status update (RUNNING, FINISHED, PAUSED, etc.)."""
        message = {
            "type": MessageType.STATUS.value,
            "job": job_name,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcast_to_job(job_name, message)
    
    async def send_completion(self, job_name: str, success: bool, summary: Dict[str, Any]):
        """Send job completion message with summary."""
        message = {
            "type": MessageType.COMPLETION.value,
            "job": job_name,
            "success": success,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Clear latest progress on completion
        if job_name in self.latest_progress:
            del self.latest_progress[job_name]
        
        await self._broadcast_to_job(job_name, message)
    
    async def _broadcast_to_job(self, job_name: str, message: Dict[str, Any]):
        """Broadcast message to all connections for a specific job."""
        if job_name not in self.connections:
            logger.debug(f"No WebSocket connections for job '{job_name}'")
            return
        
        message_text = json.dumps(message)
        disconnected_clients = []
        
        for websocket in self.connections[job_name]:
            try:
                await websocket.send_text(message_text)
            except WebSocketDisconnect:
                disconnected_clients.append(websocket)
            except Exception as e:
                logger.warning("[WS] Failed to send message to WebSocket client", error=str(e))
                disconnected_clients.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected_clients:
            self.disconnect(websocket, job_name)
    
    def get_connection_count(self, job_name: str) -> int:
        """Get number of active connections for a job."""
        return len(self.connections.get(job_name, []))
    
    def get_total_connections(self) -> int:
        """Get total number of active WebSocket connections."""
        return sum(len(connections) for connections in self.connections.values())
    
    def clear_job_progress(self, job_name: str):
        """Clear stored progress for a job (useful on job start)."""
        if job_name in self.latest_progress:
            del self.latest_progress[job_name]

    async def broadcast_to_client(self, tenant_id: int, message: Dict[str, Any]):
        """Send a message to all WebSocket connections (for client-wide updates like color schema)."""
        total_sent = 0
        message_text = json.dumps(message)

        # Send to all job connections (since we don't track tenant_id per connection)
        for job_name, websockets in list(self.connections.items()):
            disconnected_clients = []

            for websocket in websockets:
                try:
                    await websocket.send_text(message_text)
                    total_sent += 1
                except WebSocketDisconnect:
                    disconnected_clients.append(websocket)
                except Exception as e:
                    logger.warning("[WS] Failed to send color schema update to WebSocket client", error=str(e))
                    disconnected_clients.append(websocket)

            # Clean up disconnected clients
            for websocket in disconnected_clients:
                self.disconnect(websocket, job_name)

        if total_sent > 0:
            logger.info("[COLOR] Broadcasted color schema update", total_connections=total_sent)
        else:
            logger.debug("No active WebSocket connections to broadcast color schema update")

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Send a message to all active WebSocket connections."""
        await self.broadcast_to_client(0, message)  # Use 0 as a placeholder tenant_id


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return websocket_manager
