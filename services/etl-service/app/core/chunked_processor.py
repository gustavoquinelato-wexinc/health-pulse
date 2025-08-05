"""
Chunked Bulk Processor for ETL Operations
Process large datasets in smaller, manageable chunks to prevent long-running transactions.
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional
from contextlib import contextmanager
from sqlalchemy.orm import Session

from app.core.database import get_database

logger = logging.getLogger(__name__)


class ChunkedBulkProcessor:
    """
    Process large datasets in smaller, manageable chunks
    to prevent long-running transactions and improve concurrency.
    """
    
    def __init__(self, chunk_size: int = 100, commit_frequency: int = 5):
        """
        Initialize the chunked processor.
        
        Args:
            chunk_size: Number of records to process in each chunk
            commit_frequency: Commit every N chunks
        """
        self.chunk_size = chunk_size
        self.commit_frequency = commit_frequency
    
    async def process_bulk_data(
        self, 
        data_list: List[Dict[str, Any]], 
        processor_func: Callable,
        progress_callback: Optional[Callable] = None,
        job_name: str = "bulk_operation"
    ):
        """
        Process data in chunks with periodic commits.
        
        Args:
            data_list: List of data items to process
            processor_func: Function to process each chunk (session, chunk)
            progress_callback: Optional callback for progress updates
            job_name: Name of the job for logging
        """
        database = get_database()
        chunks_processed = 0
        total_chunks = (len(data_list) + self.chunk_size - 1) // self.chunk_size
        
        logger.info(f"Starting chunked processing: {len(data_list)} items in {total_chunks} chunks")
        
        for i in range(0, len(data_list), self.chunk_size):
            chunk = data_list[i:i + self.chunk_size]
            chunk_number = chunks_processed + 1
            
            # Use ETL session context for optimized bulk operations
            with database.get_etl_session_context() as session:
                try:
                    await processor_func(session, chunk)
                    chunks_processed += 1
                    
                    # Progress logging
                    progress_pct = (chunks_processed / total_chunks) * 100
                    logger.info(f"{job_name}: Processed chunk {chunk_number}/{total_chunks} ({progress_pct:.1f}%)")
                    
                    # Progress callback
                    if progress_callback:
                        await progress_callback(chunks_processed, total_chunks, f"Processing chunk {chunk_number}")
                    
                    # Yield control to prevent UI blocking
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Error processing chunk {chunk_number}: {e}")
                    raise
        
        logger.info(f"Chunked processing completed: {chunks_processed} chunks processed")


class AsyncYieldManager:
    """Manage async yielding to prevent UI blocking"""
    
    def __init__(self, yield_frequency: int = 10, yield_duration: float = 0.01):
        """
        Initialize the yield manager.
        
        Args:
            yield_frequency: Yield control every N operations
            yield_duration: Duration to yield in seconds
        """
        self.yield_frequency = yield_frequency
        self.yield_duration = yield_duration
        self.operation_count = 0
    
    async def yield_if_needed(self):
        """Yield control if frequency threshold reached"""
        self.operation_count += 1
        
        if self.operation_count % self.yield_frequency == 0:
            await asyncio.sleep(self.yield_duration)
    
    async def yield_with_progress(
        self, 
        current: int, 
        total: int, 
        websocket_manager=None, 
        job_name: str = None
    ):
        """Yield with progress update"""
        await self.yield_if_needed()
        
        if websocket_manager and job_name:
            progress = (current / total) * 100
            await websocket_manager.send_progress_update(
                job_name, progress, f"Processing {current}/{total}"
            )


# Example usage functions for GitHub and Jira jobs
async def process_github_prs_chunked(repository_data: Dict[str, Any], prs_data: List[Dict[str, Any]]):
    """Example: Process GitHub PRs using chunked processing"""
    
    async def process_pr_chunk(session: Session, pr_chunk: List[Dict[str, Any]]):
        """Process a chunk of PRs"""
        for pr_data in pr_chunk:
            # Process individual PR
            # This would contain the actual PR processing logic
            logger.debug(f"Processing PR: {pr_data.get('number', 'unknown')}")
            
            # Simulate processing time
            await asyncio.sleep(0.001)
    
    # Create chunked processor
    processor = ChunkedBulkProcessor(chunk_size=50, commit_frequency=3)
    
    # Process PRs in chunks
    await processor.process_bulk_data(
        prs_data, 
        process_pr_chunk,
        job_name=f"github_prs_{repository_data.get('name', 'unknown')}"
    )


async def process_jira_issues_chunked(project_data: Dict[str, Any], issues_data: List[Dict[str, Any]]):
    """Example: Process Jira issues using chunked processing"""
    
    async def process_issue_chunk(session: Session, issue_chunk: List[Dict[str, Any]]):
        """Process a chunk of issues"""
        for issue_data in issue_chunk:
            # Process individual issue
            # This would contain the actual issue processing logic
            logger.debug(f"Processing issue: {issue_data.get('key', 'unknown')}")
            
            # Simulate processing time
            await asyncio.sleep(0.001)
    
    # Create chunked processor
    processor = ChunkedBulkProcessor(chunk_size=100, commit_frequency=5)
    
    # Process issues in chunks
    await processor.process_bulk_data(
        issues_data, 
        process_issue_chunk,
        job_name=f"jira_issues_{project_data.get('key', 'unknown')}"
    )


# Utility function to create optimized session contexts
@contextmanager
def get_optimized_etl_session():
    """Get an optimized session for ETL operations"""
    database = get_database()
    with database.get_etl_session_context() as session:
        yield session


@contextmanager  
def get_optimized_read_session():
    """Get an optimized session for read operations"""
    database = get_database()
    with database.get_read_session_context() as session:
        yield session
