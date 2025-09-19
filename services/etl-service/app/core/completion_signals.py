"""
Completion signals for coordinating between webhook handlers and waiting jobs.
This module provides a way for webhook completion handlers to signal waiting jobs
that processing has completed, avoiding race conditions with database polling.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Global completion signals storage
_completion_signals: Dict[str, Dict[str, Any]] = {}
_completion_events: Dict[str, asyncio.Event] = {}

async def set_vectorization_completion_signal(tenant_id: int, completion_data: Dict[str, Any]):
    """
    Set a completion signal for vectorization job.
    
    Args:
        tenant_id: Tenant ID for the completed vectorization
        completion_data: Data about the completion (items processed, etc.)
    """
    try:
        signal_key = f"vectorization_{tenant_id}"
        
        # Store completion data
        _completion_signals[signal_key] = {
            'completed_at': datetime.utcnow().isoformat(),
            'tenant_id': tenant_id,
            **completion_data
        }
        
        # Set the event to wake up any waiting jobs
        if signal_key not in _completion_events:
            _completion_events[signal_key] = asyncio.Event()
        
        _completion_events[signal_key].set()
        
        logger.info(f"[COMPLETION_SIGNAL] Set vectorization completion signal for tenant {tenant_id}")
        
    except Exception as e:
        logger.error(f"[COMPLETION_SIGNAL] Error setting completion signal: {e}")

async def wait_for_vectorization_completion(tenant_id: int, timeout_seconds: int = 1800) -> Optional[Dict[str, Any]]:
    """
    Wait for vectorization completion signal.
    
    Args:
        tenant_id: Tenant ID to wait for
        timeout_seconds: Maximum time to wait (default: 30 minutes)
        
    Returns:
        Completion data if received, None if timeout
    """
    try:
        signal_key = f"vectorization_{tenant_id}"
        
        # Create event if it doesn't exist
        if signal_key not in _completion_events:
            _completion_events[signal_key] = asyncio.Event()
        
        logger.info(f"[COMPLETION_SIGNAL] Waiting for vectorization completion signal for tenant {tenant_id} (timeout: {timeout_seconds}s)")
        
        # Wait for the completion signal with timeout
        try:
            await asyncio.wait_for(_completion_events[signal_key].wait(), timeout=timeout_seconds)
            
            # Get completion data
            completion_data = _completion_signals.get(signal_key)
            if completion_data:
                logger.info(f"[COMPLETION_SIGNAL] Received vectorization completion signal for tenant {tenant_id}")
                return completion_data
            else:
                logger.warning(f"[COMPLETION_SIGNAL] Event set but no completion data found for tenant {tenant_id}")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"[COMPLETION_SIGNAL] Timeout waiting for vectorization completion signal for tenant {tenant_id}")
            return None
            
    except Exception as e:
        logger.error(f"[COMPLETION_SIGNAL] Error waiting for completion signal: {e}")
        return None

def clear_vectorization_completion_signal(tenant_id: int):
    """
    Clear completion signal for a tenant (cleanup after job completion).
    
    Args:
        tenant_id: Tenant ID to clear signal for
    """
    try:
        signal_key = f"vectorization_{tenant_id}"
        
        # Clear completion data
        if signal_key in _completion_signals:
            del _completion_signals[signal_key]
        
        # Clear and remove event
        if signal_key in _completion_events:
            _completion_events[signal_key].clear()
            del _completion_events[signal_key]
        
        logger.debug(f"[COMPLETION_SIGNAL] Cleared vectorization completion signal for tenant {tenant_id}")
        
    except Exception as e:
        logger.error(f"[COMPLETION_SIGNAL] Error clearing completion signal: {e}")

def get_completion_signal_status() -> Dict[str, Any]:
    """
    Get status of all completion signals (for debugging).
    
    Returns:
        Dict with current signal status
    """
    return {
        'active_signals': list(_completion_signals.keys()),
        'active_events': list(_completion_events.keys()),
        'signal_count': len(_completion_signals),
        'event_count': len(_completion_events)
    }
