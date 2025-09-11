"""
Logging endpoints for ETL service.
Provides access to application logs and log management.
"""

import os
import zipfile
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from typing import Optional, List, Iterator
from datetime import datetime, timedelta
import io
from app.auth.centralized_auth_middleware import UserData, require_authentication

router = APIRouter()

# ANSI escape sequence pattern for cleaning log files
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def clean_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return ANSI_ESCAPE.sub('', text)




# Log file configuration - Use the actual ETL service logs directory
LOG_DIR = Path("services/etl-service/logs")
LOG_FILE = LOG_DIR / "etl_service.log"

# Fallback to local logs directory if the service-specific one doesn't exist
if not LOG_DIR.exists():
    LOG_DIR = Path("logs")
    LOG_FILE = LOG_DIR / "etl_service.log"


@router.get("/logs/recent")
async def get_recent_logs(
    lines: int = Query(100, ge=1, le=10000, description="Number of recent log lines to return"),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    search: Optional[str] = Query(None, description="Search for specific text in logs"),
    user: UserData = Depends(require_authentication)
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
                "message": f"Log file not found at: {LOG_FILE}"
            }

        # Read the last N lines from the log file with error handling
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            # Fallback to latin-1 encoding if UTF-8 fails
            with open(LOG_FILE, 'r', encoding='latin-1') as f:
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
        # Log the actual error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error reading logs from {LOG_FILE}: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to read logs from {LOG_FILE}: {str(e)}"
        )


def create_zip_stream(file_path: Path, chunk_size: int = 8192) -> Iterator[bytes]:
    """Create a ZIP file stream containing the log file."""
    try:
        # Create an in-memory ZIP file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
            # Add the log file to the ZIP
            zip_file.write(file_path, file_path.name)

        # Reset buffer position to beginning
        zip_buffer.seek(0)

        # Stream the ZIP file in chunks
        while chunk := zip_buffer.read(chunk_size):
            yield chunk

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating ZIP file: {str(e)}")


@router.get("/logs/download/{filename}")
async def download_log_file(
    filename: str,
    compress: bool = Query(True, description="Compress log file as ZIP (recommended for large files)"),
    clean: bool = Query(True, description="Remove ANSI color codes for better readability"),
    user: UserData = Depends(require_authentication)
):
    """
    Download a specific log file by filename with optional ZIP compression and ANSI cleaning.

    Args:
        filename: Name of the log file to download
        compress: Whether to compress the file as ZIP (default: True)
        clean: Whether to remove ANSI color codes (default: True)

    Returns:
        StreamingResponse: Log file download (ZIP or plain text)
    """
    try:
        # Validate filename to prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        log_file = LOG_DIR / filename
        if not log_file.exists():
            raise HTTPException(status_code=404, detail=f"Log file '{filename}' not found")

        # Get file size
        file_size = log_file.stat().st_size

        if compress:
            # Create ZIP file and stream it
            suffix = "_clean" if clean else "_raw"
            zip_filename = f"{log_file.stem}{suffix}.zip"

            # Create the ZIP stream
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                if clean:
                    # Read file, clean ANSI codes, and add to ZIP
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    cleaned_content = clean_ansi_codes(content)
                    zip_file.writestr(f"{log_file.stem}_clean.log", cleaned_content)
                else:
                    # Add raw file to ZIP
                    zip_file.write(log_file, log_file.name)

            zip_data = zip_buffer.getvalue()
            zip_size = len(zip_data)

            return StreamingResponse(
                io.BytesIO(zip_data),
                media_type='application/zip',
                headers={
                    "Content-Disposition": f"attachment; filename={zip_filename}",
                    "Content-Length": str(zip_size),
                    "Cache-Control": "no-cache"
                }
            )
        else:
            # Check file size limit for uncompressed files (50MB max)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Uncompressed log file too large ({file_size / 1024 / 1024:.1f}MB). Use compression or download a smaller file."
                )

            # Stream uncompressed file
            if clean:
                # Read, clean, and stream
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                cleaned_content = clean_ansi_codes(content)
                cleaned_bytes = cleaned_content.encode('utf-8')

                suffix = "_clean"
                filename_clean = f"{log_file.stem}{suffix}.log"

                return StreamingResponse(
                    io.BytesIO(cleaned_bytes),
                    media_type='text/plain',
                    headers={
                        "Content-Disposition": f"attachment; filename={filename_clean}",
                        "Content-Length": str(len(cleaned_bytes)),
                        "Cache-Control": "no-cache"
                    }
                )
            else:
                # Stream raw file
                def file_streamer():
                    with open(log_file, 'rb') as file:
                        while chunk := file.read(8192):
                            yield chunk

                return StreamingResponse(
                    file_streamer(),
                    media_type='text/plain',
                    headers={
                        "Content-Disposition": f"attachment; filename={log_file.name}",
                        "Cache-Control": "no-cache"
                    }
                )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download log file: {str(e)}")


@router.get("/logs/download")
async def download_logs(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format for specific log file"),
    compress: bool = Query(True, description="Compress log file as ZIP (recommended for large files)"),
    clean: bool = Query(True, description="Remove ANSI color codes for better readability"),
    user: UserData = Depends(require_authentication)
):
    """
    Download log files with optional ZIP compression and ANSI cleaning.

    Args:
        date: Optional date for specific log file
        compress: Whether to compress the file as ZIP (default: True)
        clean: Whether to remove ANSI color codes (default: True)

    Returns:
        StreamingResponse: Log file download (ZIP or plain text)
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

        # Get file size
        file_size = log_file.stat().st_size

        if compress:
            # Create ZIP file and stream it
            suffix = "_clean" if clean else "_raw"
            zip_filename = f"{log_file.stem}{suffix}.zip"

            # Create the ZIP stream
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                if clean:
                    # Read file, clean ANSI codes, and add to ZIP
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    cleaned_content = clean_ansi_codes(content)
                    zip_file.writestr(f"{log_file.stem}_clean.log", cleaned_content)
                else:
                    # Add raw file to ZIP
                    zip_file.write(log_file, log_file.name)

            zip_data = zip_buffer.getvalue()
            zip_size = len(zip_data)

            return StreamingResponse(
                io.BytesIO(zip_data),
                media_type='application/zip',
                headers={
                    "Content-Disposition": f"attachment; filename={zip_filename}",
                    "Content-Length": str(zip_size),
                    "Cache-Control": "no-cache"
                }
            )
        else:
            # Check file size limit for uncompressed files (50MB max)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Uncompressed log file too large ({file_size / 1024 / 1024:.1f}MB). Use compression or download a smaller file."
                )

            # Stream uncompressed file
            if clean:
                # Read, clean, and stream
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                cleaned_content = clean_ansi_codes(content)
                cleaned_bytes = cleaned_content.encode('utf-8')

                suffix = "_clean"
                filename = f"{log_file.stem}{suffix}.log"

                return StreamingResponse(
                    io.BytesIO(cleaned_bytes),
                    media_type='text/plain',
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "Content-Length": str(len(cleaned_bytes)),
                        "Cache-Control": "no-cache"
                    }
                )
            else:
                # Stream raw file
                def file_streamer():
                    with open(log_file, 'rb') as file:
                        while chunk := file.read(8192):
                            yield chunk

                return StreamingResponse(
                    file_streamer(),
                    media_type='text/plain',
                    headers={
                        "Content-Disposition": f"attachment; filename={log_file.name}",
                        "Cache-Control": "no-cache"
                    }
                )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download logs: {str(e)}")


@router.get("/logs/tail")
async def tail_logs(
    lines: int = Query(50, ge=1, le=1000, description="Number of lines to tail"),
    user: UserData = Depends(require_authentication)
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
async def list_log_files(user: UserData = Depends(require_authentication)):
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
    days: int = Query(30, ge=0, le=365, description="Delete log files older than N days (0 = all logs)"),
    user: UserData = Depends(require_authentication)
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
        
        deleted_files = []
        cleared_files = []

        # Handle "All" option (days=0) vs specific days
        if days == 0:
            # Delete ALL log files (except active one which gets cleared)
            for file_path in LOG_DIR.glob("*.log"):
                stat = file_path.stat()
                file_date = datetime.fromtimestamp(stat.st_mtime)
                file_size = stat.st_size

                if file_path.name == LOG_FILE.name:
                    # Clear the active log file content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('')
                    cleared_files.append({
                        "filename": file_path.name,
                        "size_bytes": file_size,
                        "modified_at": file_date.isoformat()
                    })
                else:
                    # Delete non-active log files
                    file_path.unlink()
                    deleted_files.append({
                        "filename": file_path.name,
                        "size_bytes": file_size,
                        "modified_at": file_date.isoformat()
                    })
        else:
            # Delete files older than specified days
            cutoff_date = datetime.now() - timedelta(days=days)

            for file_path in LOG_DIR.glob("*.log"):
                # Skip current log file for age-based cleanup
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
        
        total_size_freed = sum(f['size_bytes'] for f in deleted_files) + sum(f['size_bytes'] for f in cleared_files)

        response_data = {
            "deleted_files": deleted_files,
            "cleared_files": cleared_files,
            "total_files_deleted": len(deleted_files),
            "total_files_cleared": len(cleared_files),
            "total_size_freed_mb": round(total_size_freed / (1024 * 1024), 2),
            "days_threshold": days
        }

        # Add cutoff_date only for age-based cleanup
        if days > 0:
            cutoff_date = datetime.now() - timedelta(days=days)
            response_data["cutoff_date"] = cutoff_date.isoformat()

        return response_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup logs: {str(e)}")


@router.delete("/logs/file/{filename}")
async def delete_log_file(
    filename: str,
    user: UserData = Depends(require_authentication)
):
    """
    Delete a specific log file.

    Args:
        filename: Name of the log file to delete

    Returns:
        dict: Confirmation of deletion
    """
    try:
        # Validate filename to prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        log_file = LOG_DIR / filename

        if not log_file.exists():
            raise HTTPException(status_code=404, detail=f"Log file '{filename}' not found")

        # Handle active log file differently - clear content instead of delete
        if log_file.samefile(LOG_FILE):
            # Clear the content of the active log file
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('')  # Clear the file content

            return {
                "filename": filename,
                "message": f"Successfully cleared content of active log file '{filename}'",
                "action": "cleared"
            }

        # Delete the file (non-active log files)
        log_file.unlink()

        return {
            "filename": filename,
            "message": f"Successfully deleted log file '{filename}'",
            "action": "deleted"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete log file: {str(e)}")
