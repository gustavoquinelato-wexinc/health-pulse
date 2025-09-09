"""
WebSocket API routes for real-time job monitoring.

Provides WebSocket endpoints for:
- Real-time progress updates
- Exception/error logging
- Job status changes
- Completion notifications
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from app.core.websocket_manager import get_websocket_manager, WebSocketManager
from app.core.logging_config import get_logger
from app.api.web_routes import verify_token
import json

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/progress/{job_name}")
async def job_progress_websocket(websocket: WebSocket, job_name: str):
    """
    WebSocket endpoint for real-time job progress monitoring.

    Args:
        websocket: WebSocket connection
        job_name: Name of the job to monitor (Jira, GitHub, orchestrator)

    Message Types:
        - progress: Real-time progress updates with percentage and step
        - exception: Error/warning messages only
        - status: Job status changes (RUNNING, FINISHED, etc.)
        - completion: Job completion with summary
    """
    # Log the incoming connection attempt
    logger.info("[WS] Connection attempt", job_name=job_name, raw=True)

    # URL decode job name to handle spaces (e.g., "WEX%20Fabric" -> "WEX Fabric")
    import urllib.parse
    decoded_job_name = urllib.parse.unquote(job_name)
    logger.info("[WS] Job name decoded", original=job_name, decoded=decoded_job_name)

    # Validate job name - accept both display names and internal names for compatibility
    valid_jobs = ['jira', 'jira_sync', 'github', 'github_sync', 'wex fabric', 'fabric_sync', 'wex ad', 'ad_sync', 'orchestrator']
    if decoded_job_name.lower() not in valid_jobs:
        logger.warning("[WS] Invalid job name", job_name=decoded_job_name, valid_jobs=valid_jobs)
        await websocket.close(code=4000, reason=f"Invalid job name. Valid jobs: {valid_jobs}")
        return

    # Use decoded job name from here on
    job_name = decoded_job_name

    websocket_manager = get_websocket_manager()

    try:
        # Register client (this will accept the WebSocket connection)
        await websocket_manager.connect(websocket, job_name)
        
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
                    logger.warning(f"Invalid JSON received from WebSocket client: {data}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket connection for job '{job_name}': {e}")
                break
                
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for job '{job_name}': {e}")
    finally:
        # Clean up connection
        websocket_manager.disconnect(websocket, job_name)


@router.get("/api/v1/websocket/status")
async def websocket_status(token: str = Depends(verify_token)):
    """
    Get WebSocket connection status and statistics.
    
    Returns:
        dict: WebSocket connection statistics
    """
    websocket_manager = get_websocket_manager()
    
    # Get connection counts per job
    job_connections = {}
    for job_name in ['Jira', 'GitHub', 'WEX Fabric', 'WEX AD', 'orchestrator']:
        job_connections[job_name] = websocket_manager.get_connection_count(job_name)
    
    return {
        "total_connections": websocket_manager.get_total_connections(),
        "job_connections": job_connections,
        "active_jobs": list(websocket_manager.connections.keys()),
        "latest_progress_available": list(websocket_manager.latest_progress.keys())
    }


@router.post("/api/v1/websocket/test/{job_name}")
async def test_websocket_message(job_name: str, token: str = Depends(verify_token)):
    """
    Test endpoint to send sample WebSocket messages.
    Useful for testing WebSocket functionality.

    Args:
        job_name: Job to send test message to
    """
    # URL decode job name to handle spaces (e.g., "WEX%20Fabric" -> "WEX Fabric")
    import urllib.parse
    job_name = urllib.parse.unquote(job_name)

    valid_jobs = ['Jira', 'jira_sync', 'GitHub', 'github_sync', 'WEX Fabric', 'fabric_sync', 'WEX AD', 'ad_sync', 'orchestrator']
    if job_name not in valid_jobs:
        raise HTTPException(status_code=400, detail=f"Invalid job name. Valid jobs: {valid_jobs}")
    
    websocket_manager = get_websocket_manager()
    
    # Send test progress update
    await websocket_manager.send_progress_update(
        job_name=job_name,
        percentage=75.5,
        step="Test progress update from API"
    )
    
    # Send test exception
    await websocket_manager.send_exception(
        job_name=job_name,
        level="INFO",
        message="Test exception message from API",
        error_details="This is a test message to verify WebSocket functionality"
    )
    
    return {
        "success": True,
        "message": f"Test messages sent to {job_name} WebSocket clients",
        "connections": websocket_manager.get_connection_count(job_name)
    }
