"""
WebSocket API routes for real-time ETL job monitoring.

Provides WebSocket endpoints for:
- Real-time progress updates
- Job status changes
- Completion notifications
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from app.core.logging_config import get_logger
from typing import Dict, List
import json
import asyncio

router = APIRouter()
logger = get_logger(__name__)

# Global WebSocket manager
class WebSocketManager:
    """Manages WebSocket connections for ETL job progress updates with tenant isolation"""

    def __init__(self):
        # Store connections by tenant-job key: "tenant_id:job_name"
        self.connections: Dict[str, List[WebSocket]] = {}
        # Store latest progress for each tenant-job
        self.latest_progress: Dict[str, dict] = {}

    def _get_tenant_job_key(self, tenant_id: int, job_name: str) -> str:
        """Generate tenant-isolated key for job connections."""
        return f"{tenant_id}:{job_name}"

    async def connect(self, websocket: WebSocket, tenant_id: int, job_name: str):
        """Accept a new WebSocket connection for a specific tenant's job."""
        await websocket.accept()

        tenant_job_key = self._get_tenant_job_key(tenant_id, job_name)

        if tenant_job_key not in self.connections:
            self.connections[tenant_job_key] = []

        self.connections[tenant_job_key].append(websocket)
        logger.info(f"[WS] ✅ Service connected: tenant {tenant_id} job '{job_name}' (connections: {len(self.connections[tenant_job_key])})")

        # Send latest progress if available
        if tenant_job_key in self.latest_progress:
            try:
                await websocket.send_text(json.dumps(self.latest_progress[tenant_job_key]))
            except Exception as e:
                logger.warning(f"[WS] Failed to send latest progress to new connection: {e}")

    async def disconnect(self, websocket: WebSocket, tenant_id: int, job_name: str):
        """Remove a WebSocket connection."""
        tenant_job_key = self._get_tenant_job_key(tenant_id, job_name)

        if tenant_job_key in self.connections:
            try:
                self.connections[tenant_job_key].remove(websocket)
                remaining_connections = len(self.connections[tenant_job_key])

                # Clean up empty job lists
                if not self.connections[tenant_job_key]:
                    del self.connections[tenant_job_key]
                    logger.info(f"[WS] 🔌 Service disconnected: tenant {tenant_id} job '{job_name}' (no more connections)")
                else:
                    logger.info(f"[WS] 🔌 Service disconnected: tenant {tenant_id} job '{job_name}' (remaining: {remaining_connections})")
            except ValueError:
                pass  # Connection already removed
    
    async def send_progress_update(self, tenant_id: int, job_name: str, percentage: float, message: str):
        """Send progress update to all connected clients for a tenant's job."""
        tenant_job_key = self._get_tenant_job_key(tenant_id, job_name)

        if tenant_job_key not in self.connections:
            return

        progress_data = {
            "type": "progress",
            "job": job_name,
            "percentage": percentage,
            "step": message,
            "timestamp": asyncio.get_event_loop().time()
        }

        # Store latest progress
        self.latest_progress[tenant_job_key] = progress_data

        # Send to all connected clients for this tenant's job
        disconnected = []
        for websocket in self.connections[tenant_job_key]:
            try:
                await websocket.send_text(json.dumps(progress_data))
            except Exception as e:
                logger.warning(f"[WS] Failed to send progress to client: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            await self.disconnect(ws, tenant_id, job_name)
    
    async def send_status_update(self, tenant_id: int, job_name: str, status: str, message: str = None):
        """Send status update to all connected clients for a tenant's job."""
        tenant_job_key = self._get_tenant_job_key(tenant_id, job_name)

        if tenant_job_key not in self.connections:
            return

        status_data = {
            "type": "status",
            "job": job_name,
            "status": status,
            "message": message,
            "timestamp": asyncio.get_event_loop().time()
        }

        # Send to all connected clients for this tenant's job
        disconnected = []
        for websocket in self.connections[tenant_job_key]:
            try:
                await websocket.send_text(json.dumps(status_data))
            except Exception as e:
                logger.warning(f"[WS] Failed to send status to client: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            await self.disconnect(ws, tenant_id, job_name)
    
    async def send_completion_update(self, tenant_id: int, job_name: str, success: bool, summary: dict):
        """Send completion update to all connected clients for a tenant's job."""
        tenant_job_key = self._get_tenant_job_key(tenant_id, job_name)

        if tenant_job_key not in self.connections:
            return

        completion_data = {
            "type": "completion",
            "job": job_name,
            "success": success,
            "summary": summary,
            "timestamp": asyncio.get_event_loop().time()
        }

        # Send to all connected clients for this tenant's job
        disconnected = []
        for websocket in self.connections[tenant_job_key]:
            try:
                await websocket.send_text(json.dumps(completion_data))
            except Exception as e:
                logger.warning(f"[WS] Failed to send completion to client: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            await self.disconnect(ws, tenant_id, job_name)
    
    def get_connection_count(self, tenant_id: int, job_name: str) -> int:
        """Get number of connections for a tenant's job."""
        tenant_job_key = self._get_tenant_job_key(tenant_id, job_name)
        return len(self.connections.get(tenant_job_key, []))

    def get_total_connections(self) -> int:
        """Get total number of connections across all tenant-jobs."""
        return sum(len(connections) for connections in self.connections.values())

    def get_tenant_job_connections(self) -> Dict[str, int]:
        """Get connection counts by tenant-job key."""
        return {key: len(connections) for key, connections in self.connections.items()}

# Global instance
websocket_manager = WebSocketManager()

def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return websocket_manager


@router.websocket("/ws/progress/{job_name}")
async def websocket_progress_endpoint(websocket: WebSocket, job_name: str, tenant_id: int = Query(1)):
    """
    Service-to-service WebSocket endpoint for real-time job progress updates.

    Args:
        job_name: Name of the ETL job to monitor (e.g., "Jira", "GitHub")
        tenant_id: Tenant ID for isolation (defaults to 1, can be overridden)

    Note: This is a service-to-service connection - no user authentication required.
    ETL jobs run autonomously and need real-time communication regardless of user login.
    """
    logger.info(f"[WS] Service-to-service WebSocket connection for tenant {tenant_id} job: {job_name}")

    try:
        # Register client (this will accept the WebSocket connection)
        await websocket_manager.connect(websocket, tenant_id, job_name)

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                data = await websocket.receive_text()

                # Handle client messages if needed
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    logger.warning(f"[WS] Invalid JSON received from client: {data}")

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"[WS] Error in WebSocket connection for tenant {tenant_id} job '{job_name}': {e}")
                break

    finally:
        # Clean up connection
        await websocket_manager.disconnect(websocket, tenant_id, job_name)


@router.get("/api/v1/websocket/status")
async def websocket_status(active_jobs: bool = Query(False), tenant_id: int = Query(1)):
    """
    Get WebSocket connection status and statistics with tenant isolation.

    Args:
        active_jobs: If True, include active jobs for service discovery
        tenant_id: Tenant ID for active jobs query

    Returns:
        dict: WebSocket connection statistics
    """
    # Get tenant-job connection information
    tenant_job_connections = websocket_manager.get_tenant_job_connections()

    result = {
        "total_connections": websocket_manager.get_total_connections(),
        "tenant_job_connections": tenant_job_connections,
        "active_tenant_jobs": list(websocket_manager.connections.keys()),
        "latest_progress_available": list(websocket_manager.latest_progress.keys())
    }

    # Add active jobs for service discovery if requested
    if active_jobs:
        try:
            from app.core.database import get_db_session
            from sqlalchemy import text

            db = next(get_db_session())

            # Get only active jobs for WebSocket connection
            query = text("""
                SELECT job_name, active
                FROM etl_jobs
                WHERE tenant_id = :tenant_id AND active = TRUE
                ORDER BY job_name ASC
            """)

            db_result = db.execute(query, {'tenant_id': tenant_id})
            jobs = [{"job_name": row[0], "active": row[1]} for row in db_result.fetchall()]

            result["active_jobs"] = jobs
            result["total_active"] = len(jobs)

        except Exception as e:
            logger.error(f"Error fetching active jobs: {e}")
            result["active_jobs"] = []
            result["total_active"] = 0

    return result





@router.post("/api/v1/websocket/test/{job_name}")
async def test_websocket_message(job_name: str, tenant_id: int = Query(1)):
    """
    Test endpoint to send sample WebSocket messages with tenant isolation.
    Useful for testing WebSocket functionality.

    Args:
        job_name: Job to send test message to
        tenant_id: Tenant ID for isolation (defaults to 1 for testing)
    """
    import urllib.parse
    job_name = urllib.parse.unquote(job_name)

    valid_jobs = ['Jira', 'GitHub', 'WEX Fabric', 'WEX AD']
    if job_name not in valid_jobs:
        raise HTTPException(status_code=400, detail=f"Invalid job name. Valid jobs: {valid_jobs}")

    # Send test progress update to specific tenant
    await websocket_manager.send_progress_update(tenant_id, job_name, 75.0, "Test progress message")

    connections = websocket_manager.get_connection_count(tenant_id, job_name)

    return {
        "success": True,
        "message": "Test message sent",
        "job_name": job_name,
        "tenant_id": tenant_id,
        "percentage": 75.0,
        "step": "Test progress message",
        "connections": connections
    }
