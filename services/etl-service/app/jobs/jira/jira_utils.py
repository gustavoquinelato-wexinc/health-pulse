"""
Jira ETL Utilities

Contains utility classes and functions for Jira ETL operations.
"""

import os
import time
import tempfile
import platform
from pathlib import Path
from app.core.logging_config import get_logger

# Import platform-specific locking
if platform.system() != 'Windows':
    import fcntl
else:
    import msvcrt

logger = get_logger(__name__)


class JobLockManager:
    """
    Context manager for job locking to prevent multiple instances.
    Uses file-based locking with platform-specific implementations.
    """
    
    def __init__(self, job_name: str, timeout: int = 300):
        self.job_name = job_name
        self.timeout = timeout
        self.lock_file = None
        self.lock_fd = None
        
        # Create locks directory if it doesn't exist
        self.locks_dir = Path(tempfile.gettempdir()) / "etl_locks"
        self.locks_dir.mkdir(exist_ok=True)
        
        self.lock_path = self.locks_dir / f"{job_name}.lock"
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is still running."""
        try:
            # Check if process is still running
            if platform.system() == 'Windows':
                import subprocess
                try:
                    # Use tasklist to check if PID exists
                    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'],
                                          capture_output=True, text=True, timeout=5)
                    return str(pid) in result.stdout
                except:
                    return True  # If we can't check, assume it's valid to be safe
            else:
                # Unix-like systems
                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                return True
        except (OSError, ProcessLookupError):
            return False
    
    def acquire_lock(self) -> bool:
        """Acquire the job lock."""
        try:
            # Check if lock file exists and if the process is still running
            if self.lock_path.exists():
                try:
                    with open(self.lock_path, 'r') as f:
                        lock_pid = int(f.read().strip())
                    
                    if self._is_process_running(lock_pid):
                        logger.warning(f"Job '{self.job_name}' is already running (PID: {lock_pid})")
                        return False
                    else:
                        logger.info(f"Removing stale lock file for job '{self.job_name}' (PID: {lock_pid})")
                        self.lock_path.unlink()
                except (ValueError, FileNotFoundError):
                    # Invalid lock file, remove it
                    if self.lock_path.exists():
                        self.lock_path.unlink()
            
            # Create new lock file
            self.lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            
            # Write current PID to lock file
            current_pid = os.getpid()
            os.write(self.lock_fd, str(current_pid).encode())
            
            # Apply platform-specific locking
            if platform.system() != 'Windows':
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                # Windows doesn't have fcntl, but the exclusive creation should be sufficient
                pass
            
            logger.info(f"Acquired lock for job '{self.job_name}' (PID: {current_pid})")
            return True
            
        except FileExistsError:
            logger.warning(f"Could not acquire lock for job '{self.job_name}' - file exists")
            return False
        except Exception as e:
            logger.error(f"Error acquiring lock for job '{self.job_name}': {e}")
            return False
    
    def release_lock(self):
        """Release the job lock."""
        try:
            if self.lock_fd is not None:
                if platform.system() != 'Windows':
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None
            
            if self.lock_path and self.lock_path.exists():
                self.lock_path.unlink()
                logger.info(f"Released lock for job '{self.job_name}'")
                
        except Exception as e:
            logger.error(f"Error releasing lock for job '{self.job_name}': {e}")
    
    def __enter__(self):
        """Context manager entry."""
        if not self.acquire_lock():
            raise RuntimeError(f"Could not acquire lock for job '{self.job_name}' - another instance is already running")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release_lock()
