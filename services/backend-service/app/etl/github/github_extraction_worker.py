"""
GitHub Extraction Worker - Processes GitHub-specific extraction requests.

Handles GitHub extraction message types:
- github_repositories: Extract GitHub repositories
- github_prs_commits_reviews_comments: Extract PRs with nested data

This worker is called from the extraction_worker_router based on message type.
"""

import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.models.unified_models import EtlJob
from app.etl.workers.queue_manager import QueueManager
from sqlalchemy import text

logger = get_logger(__name__)


class GitHubExtractionWorker:
    """
    Worker for processing GitHub-specific extraction requests.

    Note: This is NOT a queue consumer itself. It's called from ExtractionWorkerRouter
    which is the actual queue consumer. This class contains provider-specific logic.
    """

    def __init__(self):
        """Initialize GitHub extraction worker."""
        logger.info("Initialized GitHubExtractionWorker")

    def process_github_extraction(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Route GitHub extraction message to appropriate processor.

        Args:
            message_type: Type of GitHub extraction message
            message: Message containing extraction request details

        Returns:
            bool: True if processing succeeded
        """
        try:
            if message_type == 'github_repositories':
                # Run async method in event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self._extract_github_repositories(message))
                finally:
                    loop.close()
            elif message_type == 'github_prs_commits_reviews_comments':
                # Run async method in event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self._extract_github_prs(message))
                finally:
                    loop.close()
            else:
                logger.warning(f"Unknown GitHub extraction type: {message_type}")
                return False
        except Exception as e:
            logger.error(f"Error processing GitHub extraction message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    async def _extract_github_repositories(self, message: Dict[str, Any]) -> bool:
        """
        Extract GitHub repositories for a tenant.

        Args:
            message: Message containing extraction request details

        Returns:
            bool: True if extraction succeeded
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            last_job_item = message.get('last_job_item', False)

            logger.info(f"🚀 [GITHUB] Starting repositories extraction for tenant {tenant_id}, integration {integration_id}")

            # 🔑 Check for rate limit recovery resume date
            resume_from_pushed_date = message.get('resume_from_pushed_date')

            if resume_from_pushed_date:
                # RECOVERY MODE: Use last repo's pushed date as start_date
                logger.info(f"🔄 [RECOVERY] Resuming repository extraction from pushed date: {resume_from_pushed_date}")
                last_sync_date = resume_from_pushed_date
            else:
                # NORMAL MODE: Fetch last_sync_date from database (etl_jobs table)
                # If null, use 2 years ago as default (captures all useful data)
                database = get_database()
                last_sync_date = None
                with database.get_read_session_context() as session:
                    job = session.query(EtlJob).filter(EtlJob.id == job_id).first()
                    if job and job.last_sync_date:
                        last_sync_date = job.last_sync_date.strftime('%Y-%m-%d')
                        logger.info(f"📅 Using last_sync_date from database: {last_sync_date}")
                    else:
                        # Default: 2 years ago (captures all useful data)
                        two_years_ago = datetime.now() - timedelta(days=730)
                        last_sync_date = two_years_ago.strftime('%Y-%m-%d')
                        logger.info(f"📅 No last_sync_date in database, using 2-year default: {last_sync_date}")

            # Extract repositories using existing logic
            from app.etl.github.extraction import extract_github_repositories

            # 🔑 Extract token from message
            token = message.get('token')

            # Execute extraction
            result = await extract_github_repositories(
                integration_id, tenant_id, job_id, last_sync_date=last_sync_date, token=token
            )

            # Check for rate limit error
            if result.get('is_rate_limit'):
                logger.warning(f"⏸️ Rate limit reached during repository extraction")
                if job_id:
                    self._update_job_status_rate_limit_reached(
                        job_id,
                        tenant_id,
                        result.get('rate_limit_reset_at')
                    )
                return True  # Don't retry, don't send to DLQ

            if result.get('success'):
                logger.info(f"✅ [GITHUB] Repositories extraction completed for tenant {tenant_id}")
                logger.info(f"📊 [GITHUB] Processed {result.get('repositories_count', 0)} repositories")
                return True
            else:
                logger.error(f"❌ [GITHUB] Repositories extraction failed: {result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"💥 [GITHUB] Error extracting repositories: {e}")
            import traceback
            logger.error(f"💥 [GITHUB] Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status_failed(job_id, str(e), tenant_id)
            return False

    async def _extract_github_prs(self, message: Dict[str, Any]) -> bool:
        """Extract PRs with nested data from GitHub."""
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')

            logger.info(f"🚀 [GITHUB] Starting PRs extraction for tenant {tenant_id}, integration {integration_id}")

            # Extract PRs using existing logic
            from app.etl.github.extraction import github_prs_extraction_router

            # 🔑 Extract token from message
            token = message.get('token')

            # Execute extraction
            extraction_result = await github_prs_extraction_router(message)
            result = extraction_result.get('success', False)

            # Check for rate limit error
            if extraction_result.get('is_rate_limit'):
                logger.warning(f"⏸️ Rate limit reached during GitHub extraction")
                if job_id:
                    self._update_job_status_rate_limit_reached(
                        job_id,
                        tenant_id,
                        extraction_result.get('rate_limit_reset_at')
                    )
                return True  # Don't retry, don't send to DLQ

            if result:
                logger.info(f"✅ [GITHUB] PRs extraction completed for tenant {tenant_id}")
                return True
            else:
                logger.error(f"❌ [GITHUB] PRs extraction failed: {extraction_result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {extraction_result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"💥 [GITHUB] Error extracting PRs: {e}")
            import traceback
            logger.error(f"💥 [GITHUB] Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status_failed(job_id, str(e), tenant_id)
            return False

    def _update_job_overall_status(self, job_id: int, overall_status: str, message: str = None):
        """Update ETL job overall status (for failures or completion)."""
        try:
            database = get_database()
            with database.get_write_session_context() as session:
                # Use string formatting for overall_status to avoid parameter binding issues
                update_query = text(f"""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], '"{overall_status}"'::jsonb),
                        last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                session.execute(update_query, {
                    'job_id': job_id
                })
                session.commit()

                logger.info(f"Updated job {job_id} overall status to {overall_status}")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job overall status: {e}")

    def _update_job_status_failed(self, job_id: int, error_message: str, tenant_id: int):
        """Update ETL job status to FAILED with error message"""
        try:
            database = get_database()
            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], '"FAILED"'::jsonb),
                        error_message = :error_message,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'error_message': error_message[:500]  # Truncate to avoid DB issues
                })
                session.commit()

                logger.info(f"✅ Updated job {job_id} status to FAILED")

        except Exception as e:
            logger.error(f"❌ Failed to update job status to FAILED: {e}")

    def _update_job_status_rate_limit_reached(self, job_id: int, tenant_id: int, rate_limit_reset_at: Optional[str] = None):
        """
        Update ETL job status to RATE_LIMIT_REACHED with next_run set to rate limit reset time.

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
            rate_limit_reset_at: ISO format timestamp when rate limit resets (from checkpoint)
        """
        try:
            from app.core.utils import DateTimeHelper

            database = get_database()

            # Calculate next_run based on rate_limit_reset_at
            if rate_limit_reset_at:
                try:
                    next_run = datetime.fromisoformat(rate_limit_reset_at)
                except (ValueError, TypeError):
                    # Fallback to 1 minute if parsing fails
                    next_run = DateTimeHelper.now_default() + timedelta(minutes=1)
            else:
                # Default to 1 minute retry
                next_run = DateTimeHelper.now_default() + timedelta(minutes=1)

            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], '"RATE_LIMIT_REACHED"'::jsonb),
                        error_message = 'GitHub API rate limit reached - will resume automatically',
                        next_run = :next_run,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'next_run': next_run
                })
                session.commit()

                logger.info(f"⏸️ Updated job {job_id} status to RATE_LIMIT_REACHED, next_run: {next_run}")

        except Exception as e:
            logger.error(f"❌ Failed to update job status to RATE_LIMIT_REACHED: {e}")

