"""
Logging endpoints for ETL service.
Provides access to application logs and log management.
"""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from typing import Optional, List
from datetime import datetime, timedelta

router = APIRouter()

# Log file configuration
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"


@router.get("/logs/recent")
async def get_recent_logs(
    lines: int = Query(100, ge=1, le=10000, description="Number of recent log lines to return"),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    search: Optional[str] = Query(None, description="Search for specific text in logs")
):
    """
    Get recent log entries with optional filtering.
    
    Args:
        lines: Number of recent lines to return
        level: Optional log level filter
        search: Optional text search filter
        
    Returns:
        dict: Recent log entries with metadata
    """
    try:
        if not LOG_FILE.exists():
            return {
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found"
            }
        
        # Read the last N lines from the log file
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get the last N lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Apply filters
        filtered_lines = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
                
            # Filter by log level
            if level and level.upper() not in line.upper():
                continue
                
            # Filter by search text
            if search and search.lower() not in line.lower():
                continue
                
            filtered_lines.append(line)
        
        return {
            "logs": filtered_lines,
            "total_lines": len(filtered_lines),
            "requested_lines": lines,
            "filters": {
                "level": level,
                "search": search
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {str(e)}")


@router.get("/logs/download")
async def download_logs(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format for specific log file")
):
    """
    Download log files.
    
    Args:
        date: Optional date for specific log file
        
    Returns:
        FileResponse: Log file download
    """
    try:
        if date:
            # Download specific date log file
            log_file = LOG_DIR / f"app-{date}.log"
            if not log_file.exists():
                raise HTTPException(status_code=404, detail=f"Log file for date {date} not found")
        else:
            # Download current log file
            log_file = LOG_FILE
            if not log_file.exists():
                raise HTTPException(status_code=404, detail="Current log file not found")
        
        return FileResponse(
            path=str(log_file),
            filename=log_file.name,
            media_type='text/plain'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download logs: {str(e)}")


@router.get("/logs/tail")
async def tail_logs(
    lines: int = Query(50, ge=1, le=1000, description="Number of lines to tail")
):
    """
    Get live tail of log file (last N lines).
    
    Args:
        lines: Number of lines to return from end of file
        
    Returns:
        PlainTextResponse: Raw log content
    """
    try:
        if not LOG_FILE.exists():
            return PlainTextResponse("Log file not found")
        
        # Read the last N lines
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get the last N lines
        tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return PlainTextResponse(''.join(tail_lines))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tail logs: {str(e)}")


@router.get("/logs/files")
async def list_log_files():
    """
    List available log files.
    
    Returns:
        dict: List of available log files with metadata
    """
    try:
        if not LOG_DIR.exists():
            return {
                "files": [],
                "message": "Log directory not found"
            }
        
        log_files = []
        for file_path in LOG_DIR.glob("*.log"):
            stat = file_path.stat()
            log_files.append({
                "filename": file_path.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x['modified_at'], reverse=True)
        
        return {
            "files": log_files,
            "total_files": len(log_files),
            "log_directory": str(LOG_DIR.absolute())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list log files: {str(e)}")


@router.delete("/logs/cleanup")
async def cleanup_old_logs(
    days: int = Query(30, ge=1, le=365, description="Delete log files older than N days")
):
    """
    Clean up old log files.
    
    Args:
        days: Delete files older than this many days
        
    Returns:
        dict: Cleanup operation results
    """
    try:
        if not LOG_DIR.exists():
            return {
                "deleted_files": [],
                "message": "Log directory not found"
            }
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_files = []
        
        for file_path in LOG_DIR.glob("*.log"):
            # Skip current log file
            if file_path.name == LOG_FILE.name:
                continue
                
            stat = file_path.stat()
            file_date = datetime.fromtimestamp(stat.st_mtime)
            
            if file_date < cutoff_date:
                file_size = stat.st_size
                file_path.unlink()  # Delete the file
                deleted_files.append({
                    "filename": file_path.name,
                    "size_bytes": file_size,
                    "modified_at": file_date.isoformat()
                })
        
        total_size_freed = sum(f['size_bytes'] for f in deleted_files)
        
        return {
            "deleted_files": deleted_files,
            "total_files_deleted": len(deleted_files),
            "total_size_freed_mb": round(total_size_freed / (1024 * 1024), 2),
            "cutoff_date": cutoff_date.isoformat(),
            "days_threshold": days
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup logs: {str(e)}")
