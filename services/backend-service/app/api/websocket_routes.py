"""
WebSocket API routes for real-time ETL job monitoring.

Provides WebSocket endpoints for:
- Real-time progress updates
- Job status changes
- Completion notifications
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from app.core.logging_config import get_logger
from typing import Dict, List, Optional
import json
import asyncio
import time

router = APIRouter()
logger = get_logger(__name__)

# New Job WebSocket Manager for worker-specific channels
class JobWebSocketManager:
    """Manages WebSocket connections for worker-specific ETL job progress with tenant + job isolation"""

    def __init__(self):
        # Store connections by channel: "worker_status_tenant_{id}_job_{id}"
        self.connections: Dict[str, List[WebSocket]] = {}
        # Store latest status for each channel
        self.latest_status: Dict[str, dict] = {}

    def get_channel_name(self, worker_type: str, tenant_id: int, job_id: int) -> str:
        """Generate worker-specific channel name for tenant + job isolation."""
        return f"{worker_type}_status_tenant_{tenant_id}_job_{job_id}"

    def clear_cache(self):
        """Clear all cached WebSocket status data (useful for removing stale test data)"""
        logger.info(f"[JOB-WS] 🧹 Clearing WebSocket cache - removing {len(self.latest_status)} cached entries")
        self.latest_status.clear()

    async def connect(self, websocket: WebSocket, worker_type: str, tenant_id: int, job_id: int):
        """Accept a new WebSocket connection for a specific worker channel."""
        await websocket.accept()

        channel = self.get_channel_name(worker_type, tenant_id, job_id)

        if channel not in self.connections:
            self.connections[channel] = []

        self.connections[channel].append(websocket)
        logger.info(f"[JOB-WS] ✅ Connected to {channel} (connections: {len(self.connections[channel])})")

        # Send current worker status from database for new connections
        await self._send_current_worker_status(websocket, worker_type, tenant_id, job_id)

        # DISABLED: Don't send cached status to prevent stale test data from being sent
        # The database status is the source of truth and is sent above
        # if channel in self.latest_status:
        #     try:
        #         cached_data = self.latest_status[channel]
        #         logger.info(f"[JOB-WS] 🔍 SENDING CACHED STATUS for {channel}: {json.dumps(cached_data, indent=2)}")
        #         await websocket.send_text(json.dumps(cached_data))
        #     except Exception as e:
        #         logger.warning(f"[JOB-WS] Failed to send cached status to new connection: {e}")

    async def _send_current_worker_status(self, websocket: WebSocket, worker_type: str, tenant_id: int, job_id: int):
        """Send current job status from database to new WebSocket connection (complete JSON format)"""
        try:
            from app.core.database import get_read_session
            from sqlalchemy import text

            with get_read_session() as session:
                # Query current JSON status from database
                query = text("""
                    SELECT status
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                result = session.execute(query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id
                }).fetchone()

                if result and result[0]:
                    status_json = result[0]
                    import json as json_lib
                    status_data = json_lib.loads(status_json) if isinstance(status_json, str) else status_json

                    # Send complete database JSON structure (same format as job_status_update)
                    from app.core.utils import DateTimeHelper
                    status_message = {
                        "type": "job_status_update",
                        "tenant_id": tenant_id,
                        "job_id": job_id,
                        "status": status_data,  # Complete database JSON structure
                        "timestamp": DateTimeHelper.now_default().isoformat()
                    }

                    await websocket.send_text(json.dumps(status_message))
                    logger.info(f"[JOB-WS] Sent current job status to new {worker_type} connection")
                else:
                    # Send default status structure if no job found
                    default_status = {
                        "overall": "READY",
                        "steps": {}
                    }

                    from app.core.utils import DateTimeHelper
                    status_message = {
                        "type": "job_status_update",
                        "tenant_id": tenant_id,
                        "job_id": job_id,
                        "status": default_status,
                        "timestamp": DateTimeHelper.now_default().isoformat()
                    }

                    await websocket.send_text(json.dumps(status_message))
                    logger.info(f"[JOB-WS] Sent default job status to new {worker_type} connection")

        except Exception as e:
            logger.error(f"[JOB-WS] Failed to send current worker status: {e}")

    async def disconnect(self, websocket: WebSocket, worker_type: str, tenant_id: int, job_id: int):
        """Remove a WebSocket connection."""
        channel = self.get_channel_name(worker_type, tenant_id, job_id)

        if channel in self.connections:
            try:
                self.connections[channel].remove(websocket)
                remaining_connections = len(self.connections[channel])

                # Clean up empty channel lists
                if not self.connections[channel]:
                    del self.connections[channel]
                    logger.info(f"[JOB-WS] 🔌 Disconnected from {channel} (no more connections)")
                else:
                    logger.info(f"[JOB-WS] 🔌 Disconnected from {channel} (remaining: {remaining_connections})")
            except ValueError:
                pass  # Connection already removed

    async def send_worker_status(self, worker_type: str, tenant_id: int, job_id: int,
                                status: str, step: str, error_message: str = None):
        """
        DEPRECATED: Send worker status update to all connected clients for a specific channel.
        Use send_job_status_update() instead for consistent database JSON format.
        """
        channel = self.get_channel_name(worker_type, tenant_id, job_id)

        if channel not in self.connections:
            logger.debug(f"[JOB-WS] No connections for channel {channel}")
            return

        from app.core.utils import DateTimeHelper
        status_data = {
            "type": "worker_status",
            "worker_type": worker_type,
            "status": status,  # running, finished, failed
            "step": step,
            "tenant_id": tenant_id,
            "job_id": job_id,
            "timestamp": DateTimeHelper.now_default().isoformat(),
            "error_message": error_message
        }

        # Store latest status
        self.latest_status[channel] = status_data

        # Send to all connected clients for this channel
        disconnected = []
        for websocket in self.connections[channel]:
            try:
                await websocket.send_text(json.dumps(status_data))
                logger.debug(f"[JOB-WS] Sent {worker_type} status '{status}' to {channel}")
            except Exception as e:
                logger.warning(f"[JOB-WS] Failed to send status to client: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            await self.disconnect(ws, worker_type, tenant_id, job_id)

    async def send_job_status_update(self, tenant_id: int, job_id: int, status_json: dict):
        """Send job status update with the same JSON structure the UI reads on refresh."""
        # Send to all worker channels for this job
        worker_types = ['extraction', 'transform', 'embedding']

        for worker_type in worker_types:
            channel = self.get_channel_name(worker_type, tenant_id, job_id)

            if channel not in self.connections:
                continue

            from app.core.utils import DateTimeHelper
            status_data = {
                "type": "job_status_update",
                "tenant_id": tenant_id,
                "job_id": job_id,
                "status": status_json,  # The same JSON structure from database
                "timestamp": DateTimeHelper.now_default().isoformat()
            }

            # Store latest status
            self.latest_status[channel] = status_data

            # Send to all connected clients for this channel
            disconnected = []
            for websocket in self.connections[channel]:
                try:
                    await websocket.send_text(json.dumps(status_data))
                except Exception as e:
                    logger.warning(f"[JOB-WS] Failed to send job status to client: {e}")
                    disconnected.append(websocket)

            # Remove disconnected clients
            for ws in disconnected:
                await self.disconnect(ws, worker_type, tenant_id, job_id)

            if self.connections[channel]:  # Only log if there are connections
                logger.info(f"[JOB-WS] Sent job status update to {len(self.connections[channel])} clients on {channel}")

    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast a message to all connections on a specific channel."""
        if channel not in self.connections:
            logger.debug(f"[JOB-WS] No connections for channel {channel}")
            return

        # Store latest message
        self.latest_status[channel] = message

        # Send to all connected clients for this channel
        disconnected = []
        for websocket in self.connections[channel]:
            try:
                await websocket.send_text(json.dumps(message))
                logger.debug(f"[JOB-WS] Broadcast message to {channel}")
            except Exception as e:
                logger.warning(f"[JOB-WS] Failed to broadcast to client: {e}")
                disconnected.append(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            # Extract worker_type, tenant_id, job_id from channel name
            parts = channel.split('_')
            if len(parts) >= 6:  # worker_status_tenant_X_job_Y
                worker_type = parts[0]  # extraction/transform/embedding
                tenant_id = int(parts[3])
                job_id = int(parts[5])
                await self.disconnect(ws, worker_type, tenant_id, job_id)

# Global WebSocket managers
job_websocket_manager = JobWebSocketManager()

def get_job_websocket_manager() -> JobWebSocketManager:
    """Get the global job WebSocket manager instance."""
    return job_websocket_manager

# Legacy WebSocket manager (keeping for backward compatibility)
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
            "timestamp": time.time()
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
            "timestamp": time.time()
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
            "timestamp": time.time()
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


# Session WebSocket Manager for cross-service session synchronization
class SessionWebSocketManager:
    """
    Manages WebSocket connections for real-time session synchronization.

    Handles:
    - Logout events (instant logout across all tabs/devices)
    - Login events (sync new sessions)
    - Color schema changes (real-time theme updates)
    - Dark/Light mode changes (instant mode sync)
    """

    def __init__(self):
        # Store connections by user_id: user_id -> List[WebSocket]
        self.user_connections: Dict[int, List[WebSocket]] = {}
        logger.info("[SessionWS] 🔧 Session WebSocket Manager initialized")

    async def connect(self, websocket: WebSocket, user_id: int, user_email: str):
        """Accept a new WebSocket connection for a user's session."""
        await websocket.accept()

        if user_id not in self.user_connections:
            self.user_connections[user_id] = []

        self.user_connections[user_id].append(websocket)
        connection_count = len(self.user_connections[user_id])
        logger.info(f"[SessionWS] ✅ User connected: {user_email} (user_id={user_id}, connections={connection_count})")

    async def disconnect(self, websocket: WebSocket, user_id: int, user_email: str):
        """Remove a WebSocket connection."""
        if user_id in self.user_connections:
            try:
                self.user_connections[user_id].remove(websocket)
                remaining = len(self.user_connections[user_id])

                # Clean up empty user lists
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    logger.info(f"[SessionWS] 🔌 User disconnected: {user_email} (user_id={user_id}, no more connections)")
                else:
                    logger.info(f"[SessionWS] 🔌 User disconnected: {user_email} (user_id={user_id}, remaining={remaining})")
            except ValueError:
                pass  # Connection already removed

    async def broadcast_to_user(self, user_id: int, message: dict, event_type: str = "unknown"):
        """
        Broadcast a message to all of a user's active WebSocket connections.

        Args:
            user_id: User ID to broadcast to
            message: Message dictionary to send
            event_type: Type of event for logging (logout, login, color_change, theme_change)
        """
        if user_id not in self.user_connections:
            logger.debug(f"[SessionWS] No connections for user_id={user_id}, event={event_type}")
            return

        connections = self.user_connections[user_id]
        logger.info(f"[SessionWS] 📢 Broadcasting {event_type} to user_id={user_id} ({len(connections)} connections)")

        disconnected = []
        success_count = 0

        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
                success_count += 1
            except Exception as e:
                logger.warning(f"[SessionWS] Failed to send {event_type} to connection: {e}")
                disconnected.append(ws)

        # Remove disconnected clients
        for ws in disconnected:
            try:
                self.user_connections[user_id].remove(ws)
            except ValueError:
                pass

        # Clean up empty user lists
        if user_id in self.user_connections and not self.user_connections[user_id]:
            del self.user_connections[user_id]

        logger.info(f"[SessionWS] ✅ Broadcast complete: {success_count}/{len(connections)} successful, {len(disconnected)} failed")

    async def broadcast_logout(self, user_id: int, reason: str = "logout"):
        """Broadcast logout event to all user's connections."""
        from app.core.utils import DateTimeHelper
        message = {
            "type": "SESSION_INVALIDATED",
            "event": "logout",
            "reason": reason,
            "timestamp": DateTimeHelper.now_default().isoformat()
        }
        await self.broadcast_to_user(user_id, message, "logout")

    async def broadcast_login(self, user_id: int, user_email: str):
        """Broadcast login event to all user's connections (for multi-device sync)."""
        from app.core.utils import DateTimeHelper
        message = {
            "type": "SESSION_CREATED",
            "event": "login",
            "user_email": user_email,
            "timestamp": DateTimeHelper.now_default().isoformat()
        }
        await self.broadcast_to_user(user_id, message, "login")

    async def broadcast_color_schema_change(self, user_id: int, colors: dict):
        """Broadcast color schema change to all user's connections."""
        from app.core.utils import DateTimeHelper
        message = {
            "type": "COLOR_SCHEMA_UPDATED",
            "event": "color_change",
            "colors": colors,
            "timestamp": DateTimeHelper.now_default().isoformat()
        }
        await self.broadcast_to_user(user_id, message, "color_change")

    async def broadcast_theme_mode_change(self, user_id: int, theme_mode: str):
        """Broadcast theme mode (dark/light) change to all user's connections."""
        from app.core.utils import DateTimeHelper
        message = {
            "type": "THEME_MODE_UPDATED",
            "event": "theme_change",
            "theme_mode": theme_mode,
            "timestamp": DateTimeHelper.now_default().isoformat()
        }
        await self.broadcast_to_user(user_id, message, "theme_change")

    def get_connection_count(self, user_id: int) -> int:
        """Get number of connections for a user."""
        return len(self.user_connections.get(user_id, []))

    def get_total_connections(self) -> int:
        """Get total number of session connections across all users."""
        return sum(len(connections) for connections in self.user_connections.values())

    def get_all_connected_users(self) -> List[int]:
        """Get list of all user IDs with active connections."""
        return list(self.user_connections.keys())


# Global session WebSocket manager instance
session_websocket_manager = SessionWebSocketManager()

def get_session_websocket_manager() -> SessionWebSocketManager:
    """Get the global session WebSocket manager instance."""
    return session_websocket_manager


@router.websocket("/ws/progress/{job_name}")
async def websocket_progress_endpoint(websocket: WebSocket, job_name: str, token: str = Query(...)):
    """
    Authenticated WebSocket endpoint for real-time job progress updates.

    Args:
        job_name: Name of the ETL job to monitor (e.g., "Jira", "GitHub")
        token: JWT authentication token (required)

    Note: This endpoint requires user authentication. The tenant_id is extracted from the JWT token.
    All admins of the same tenant will see the same job progress (tenant-isolated broadcasting).
    """
    try:
        # Mask token for logging (show first 10 chars only)
        masked_token = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "***"

        # Verify token and extract tenant_id
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()

        user = await auth_service.verify_token(token, suppress_errors=True)

        if not user:
            logger.warning(f"[WS] WebSocket connection rejected: Invalid token (token={masked_token})")
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

        tenant_id = user.tenant_id
        logger.info(f"[WS] ✅ Authenticated WebSocket connection: user={user.email}, tenant={tenant_id}, job={job_name}, token={masked_token}")

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

    except Exception as e:
        logger.error(f"[WS] Error in WebSocket authentication: {e}")
        try:
            await websocket.close(code=1011, reason="Authentication error")
        except:
            pass
        return

    finally:
        # Clean up connection (only if we successfully connected)
        if 'tenant_id' in locals():
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





# New Job WebSocket Endpoints for Worker-Specific Channels

@router.websocket("/ws/job/{worker_type}/{tenant_id}/{job_id}")
async def job_websocket_endpoint(websocket: WebSocket, worker_type: str, tenant_id: int, job_id: int, token: str = Query(...)):
    """
    Authenticated WebSocket endpoint for worker-specific job progress tracking.

    Creates dedicated channels for each worker type:
    - /ws/job/extraction/{tenant_id}/{job_id} - Extraction worker status
    - /ws/job/transform/{tenant_id}/{job_id} - Transform worker status
    - /ws/job/embedding/{tenant_id}/{job_id} - Embedding worker status

    Args:
        worker_type: Type of worker (extraction, transform, embedding)
        tenant_id: Tenant ID for isolation
        job_id: Specific job ID for tracking
        token: JWT authentication token (required)
    """
    # Validate worker type
    valid_workers = ['extraction', 'transform', 'embedding']
    if worker_type not in valid_workers:
        await websocket.close(code=4000, reason=f"Invalid worker type. Valid types: {valid_workers}")
        return

    # Authenticate user with token
    try:
        masked_token = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "***"

        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()

        user = await auth_service.verify_token(token, suppress_errors=True)

        if not user:
            logger.warning(f"[JOB-WS] Connection rejected: Invalid token (token={masked_token})")
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

        logger.info(f"[JOB-WS] ✅ Authenticated WebSocket connection: user={user.email}, tenant={tenant_id}, worker={worker_type}, job={job_id}")
    except Exception as e:
        logger.error(f"[JOB-WS] Authentication error: {e}")
        await websocket.close(code=1011, reason="Authentication error")
        return

    # Connect to the job-specific channel
    await job_websocket_manager.connect(websocket, worker_type, tenant_id, job_id)

    try:
        # Keep connection alive and handle disconnection
        while True:
            # Wait for any message (ping/pong or client messages)
            try:
                data = await websocket.receive_text()
                # Echo back for ping/pong or handle client messages if needed
                logger.debug(f"[JOB-WS] Received message on {worker_type}_status_tenant_{tenant_id}_job_{job_id}: {data}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"[JOB-WS] Error in WebSocket communication: {e}")
                break

    except WebSocketDisconnect:
        pass
    finally:
        await job_websocket_manager.disconnect(websocket, worker_type, tenant_id, job_id)

# REMOVED: Test endpoint that was corrupting real job data
# The test endpoint was overriding real job status with test_step data
# causing the frontend to show "Test Step" instead of proper Jira/GitHub steps

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


@router.websocket("/ws/session")
async def websocket_session_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    Authenticated WebSocket endpoint for real-time session synchronization.

    Handles:
    - Logout events (instant logout across all tabs/devices)
    - Login events (sync new sessions)
    - Color schema changes (real-time theme updates)
    - Dark/Light mode changes (instant mode sync)

    Args:
        token: JWT authentication token (required)

    The connection stays open and receives real-time events for:
    - SESSION_INVALIDATED: User logged out (logout from any device)
    - SESSION_CREATED: User logged in (login from another device)
    - COLOR_SCHEMA_UPDATED: User changed color schema
    - THEME_MODE_UPDATED: User toggled dark/light mode
    """
    user_id = None
    user_email = None

    try:
        # Mask token for logging
        masked_token = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "***"

        # Verify token and extract user info
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()

        user = await auth_service.verify_token(token, suppress_errors=True)

        if not user:
            logger.warning(f"[SessionWS] Connection rejected: Invalid token (token={masked_token})")
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

        user_id = user.id
        user_email = user.email
        logger.info(f"[SessionWS] ✅ Authenticated connection: user={user_email}, user_id={user_id}, token={masked_token}")

        # Register client (this will accept the WebSocket connection)
        await session_websocket_manager.connect(websocket, user_id, user_email)

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                data = await websocket.receive_text()

                # Handle client messages
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        from app.core.utils import DateTimeHelper
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": DateTimeHelper.now_default().isoformat()
                        }))
                except json.JSONDecodeError:
                    logger.warning(f"[SessionWS] Invalid JSON from user {user_email}: {data}")

            except WebSocketDisconnect:
                logger.info(f"[SessionWS] Client disconnected: {user_email}")
                break
            except Exception as e:
                logger.error(f"[SessionWS] Error in connection for user {user_email}: {e}")
                break

    except Exception as e:
        logger.error(f"[SessionWS] Error in authentication: {e}")
        try:
            await websocket.close(code=1011, reason="Authentication error")
        except:
            pass
        return

    finally:
        # Clean up connection
        if user_id is not None and user_email is not None:
            await session_websocket_manager.disconnect(websocket, user_id, user_email)


@router.get("/api/v1/websocket/session/status")
async def session_websocket_status():
    """
    Get session WebSocket connection status and statistics.

    Returns:
        dict: Session WebSocket connection statistics
    """
    return {
        "total_connections": session_websocket_manager.get_total_connections(),
        "connected_users": session_websocket_manager.get_all_connected_users(),
        "user_count": len(session_websocket_manager.get_all_connected_users())
    }
