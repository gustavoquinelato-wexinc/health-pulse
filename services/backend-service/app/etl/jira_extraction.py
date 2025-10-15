"""
Jira Extraction Module for ETL Backend Service
Handles complete Jira extraction including projects, issue types, statuses, and relationships
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db_session
from app.core.logging_config import get_logger
from app.etl.jira_client import JiraAPIClient
from app.api.websocket_routes import get_websocket_manager
from app.models.unified_models import Integration

logger = get_logger(__name__)

# Project keys for WEX Health Pulse
PROJECT_KEYS = ['BDP', 'BEN', 'BEX', 'BST', 'CDB', 'CDH', 'EPE', 'FG', 'HBA', 'HDO', 'HDS', 'WCI', 'WX', 'BENBR']


class JiraExtractionProgressTracker:
    """Progress tracker for complete Jira extraction (all phases)."""

    def __init__(self, tenant_id: int, job_id: int, total_steps: int = 4):
        self.tenant_id = tenant_id
        self.job_id = job_id
        self.total_steps = total_steps
        self.websocket_manager = get_websocket_manager()

    async def update_step_progress(self, step_index: int, step_progress: float, message: str):
        """Update progress using step-based system (like old ETL service)."""
        try:
            # Calculate overall percentage using step-based system
            step_percentage = 100.0 / self.total_steps
            step_start = step_index * step_percentage
            overall_percentage = step_start + (step_progress * step_percentage)

            # Debug logging
            logger.info(f"[PROGRESS DEBUG] total_steps={self.total_steps}, step_index={step_index}, step_progress={step_progress:.2f}")
            logger.info(f"[PROGRESS DEBUG] step_percentage={step_percentage:.2f}%, step_start={step_start:.2f}%, overall={overall_percentage:.2f}%")

            # Log progress (no database update - progress is tracked in UI only)
            logger.info(f"[JIRA EXTRACTION] Step {step_index + 1}/{self.total_steps} - {overall_percentage:.1f}% - {message}")

            # Send WebSocket update
            await self.websocket_manager.send_progress_update(
                self.tenant_id, "Jira", overall_percentage, message
            )

        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

    async def complete_step(self, step_index: int, message: str):
        """Mark a step as completed."""
        await self.update_step_progress(step_index, 1.0, message)


async def execute_complete_jira_extraction(
    integration_id: int,
    tenant_id: int,
    job_id: int
) -> Dict[str, Any]:
    """
    Execute complete Jira extraction with all phases.

    Combined Flow (All Phases):
    1. Projects & Issue Types (0% -> 25%)
    2. Statuses & Project Relationships (25% -> 50%)
    3. Issues & Changelogs (50% -> 75%)
    4. Dev Status (75% -> 100%)
    """
    # Capture job start time for bounded date range extraction
    from app.core.utils import DateTimeHelper
    job_start_time = DateTimeHelper.now_default()

    progress_tracker = JiraExtractionProgressTracker(tenant_id, job_id, total_steps=3)

    try:
        # Step 1: Projects & Issue Types (0% -> 33%)
        logger.info("=" * 80)
        logger.info("STARTING STEP 1: Projects & Issue Types Extraction")
        logger.info("=" * 80)

        # Get integration and create client
        integration, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        projects_result = await _extract_projects_and_issue_types(
            jira_client, integration_id, tenant_id, progress_tracker, step_index=0
        )

        logger.info(f"✅ Step 1 completed: {projects_result['projects_count']} projects, {projects_result['issue_types_count']} issue types")

        # Step 2: Statuses & Relationships (33% -> 66%)
        logger.info("=" * 80)
        logger.info("STARTING STEP 2: Statuses & Project Relationships Extraction")
        logger.info("=" * 80)

        statuses_result = await _extract_statuses_and_relationships(
            jira_client, integration_id, tenant_id, progress_tracker, step_index=1
        )

        logger.info(f"✅ Step 2 completed: {statuses_result['statuses_count']} statuses, {statuses_result['project_relationships_count']} relationships")

        # Step 3: Issues & Changelogs (66% -> 100%)
        # Note: Dev status extraction happens in background via extraction_queue
        logger.info("=" * 80)
        logger.info("STARTING STEP 3: Issues & Changelogs Extraction")
        logger.info("=" * 80)
        logger.info(f"🔍 DEBUG: Job status should be RUNNING during Step 3")

        await progress_tracker.update_step_progress(
            2, 0.0, "Starting issues and changelogs extraction"
        )

        try:
            logger.info(f"🔍 DEBUG: About to call _extract_issues_with_changelogs_for_complete_job")
            issues_result = await _extract_issues_with_changelogs_for_complete_job(
                jira_client, integration_id, tenant_id, progress_tracker, job_id, job_start_time
            )
            logger.info(f"✅ Step 3 completed: {issues_result}")
            logger.info(f"🔍 DEBUG: Returned from _extract_issues_with_changelogs_for_complete_job - job should still be RUNNING")
        except Exception as issues_error:
            logger.error(f"❌ Step 3 (Issues extraction) failed: {issues_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        await progress_tracker.update_step_progress(
            2, 1.0, f"Completed: {issues_result.get('issues_count', 0)} issues, {issues_result.get('changelogs_count', 0)} changelogs (dev status queued in background)"
        )
        logger.info(f"🔍 DEBUG: Step 3 progress updated to 100% - job complete (dev status runs in background)")

        # Dev status extraction now happens in background via extraction_queue
        # No Step 4 needed - job completes after Step 3

        # Update job status to FINISHED and set last_sync_date to job_start_time
        logger.info(f"🔍 DEBUG: All 3 steps complete - about to call reset_job_countdown to set job to FINISHED")
        await reset_job_countdown(tenant_id, job_id, "Complete Jira extraction finished successfully", job_start_time)
        logger.info(f"🔍 DEBUG: reset_job_countdown completed - job should now be FINISHED then READY")

        logger.info("=" * 100)
        logger.info("✅ COMPLETE JIRA EXTRACTION FINISHED SUCCESSFULLY")
        logger.info(f"   Projects: {projects_result['projects_count']}")
        logger.info(f"   Issue Types: {projects_result['issue_types_count']}")
        logger.info(f"   Statuses: {statuses_result['statuses_count']}")
        logger.info(f"   Project Relationships: {statuses_result['project_relationships_count']}")
        logger.info(f"   Issues: {issues_result.get('issues_count', 0)}")
        logger.info(f"   Changelogs: {issues_result.get('changelogs_count', 0)}")
        logger.info(f"   Dev Status: Queued in background via extraction_queue")
        logger.info("=" * 100)

        return {
            "success": True,
            "projects_count": projects_result['projects_count'],
            "issue_types_count": projects_result['issue_types_count'],
            "statuses_count": statuses_result['statuses_count'],
            "project_relationships_count": statuses_result['project_relationships_count'],
            "issues_count": issues_result.get('issues_count', 0),
            "changelogs_count": issues_result.get('changelogs_count', 0)
        }

    except Exception as e:
        logger.error(f"Complete Jira extraction failed for integration {integration_id}: {e}")

        # Update job status to FAILED
        try:
            await progress_tracker.websocket_manager.send_progress_update(
                tenant_id, "Jira", 100.0, f"[ERROR] Jira extraction failed: {str(e)}"
            )

            from app.core.utils import DateTimeHelper
            from datetime import timedelta
            from app.core.database import get_database

            database = get_database()
            now = DateTimeHelper.now_default()

            # Quick READ to get retry interval
            with database.get_read_session_context() as db:
                retry_query = text("""
                    SELECT retry_interval_minutes
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                retry_result = db.execute(retry_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id
                }).fetchone()

                retry_interval = retry_result[0] if retry_result else 60

            next_run = now + timedelta(minutes=retry_interval)

            # Quick WRITE to update job status
            with database.get_write_session_context() as db:
                error_message = str(e)[:500]  # Limit error message to 500 chars
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'FAILED',
                        error_message = :error_message,
                        last_run_finished_at = NOW(),
                        next_run = :next_run,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'error_message': error_message,
                    'next_run': next_run
                })
                # Commit happens automatically

        except Exception as update_error:
            logger.error(f"Failed to update job status after error: {update_error}")

        raise


async def execute_projects_and_issue_types_extraction(
    integration_id: int,
    tenant_id: int,
    job_id: int
) -> Dict[str, Any]:
    """
    Execute projects and issue types extraction only (Phase 2.1 + 2.2).

    This is a partial extraction for manual triggering.
    For complete extraction, use execute_complete_jira_extraction().

    Combined Flow (Phase 2.1 + 2.2):
    1. Projects & Issue Types (0% -> 50%)
    2. Statuses & Project Relationships (50% -> 100%)
    """
    logger.info(f"Starting projects and issue types extraction for integration {integration_id}, tenant {tenant_id}")

    progress_tracker = JiraExtractionProgressTracker(tenant_id, job_id, total_steps=2)

    try:
        # Step 0: Projects & Issue Types (0% -> 50%)
        # Get integration and create client
        integration, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        projects_result = await _extract_projects_and_issue_types(
            jira_client, integration_id, tenant_id, progress_tracker, step_index=0
        )

        # Step 1: Statuses & Relationships (50% -> 100%)
        statuses_result = await _extract_statuses_and_relationships(
            jira_client, integration_id, tenant_id, progress_tracker, step_index=1
        )

        # Update job status to FINISHED
        await reset_job_countdown(tenant_id, job_id, "Projects and issue types extraction finished successfully")

        logger.info(f"Projects and issue types extraction completed for integration {integration_id}")

        return {
            "success": True,
            "projects_count": projects_result['projects_count'],
            "issue_types_count": projects_result['issue_types_count'],
            "statuses_count": statuses_result['statuses_count'],
            "project_relationships_count": statuses_result['project_relationships_count']
        }
        
    except Exception as e:
        logger.error(f"Complete Jira extraction failed for integration {integration_id}: {e}")

        # Update job status to FAILED
        try:
            await progress_tracker.websocket_client.send_progress_update(
                "Jira", 100.0, f"[ERROR] Jira extraction failed: {str(e)}"
            )
            
            from app.core.utils import DateTimeHelper
            from datetime import timedelta
            from app.core.database import get_database

            database = get_database()
            now = DateTimeHelper.now_default()

            # Quick READ to get retry interval
            with database.get_read_session_context() as db:
                retry_query = text("""
                    SELECT retry_interval_minutes
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                retry_result = db.execute(retry_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id
                }).fetchone()

                retry_interval_minutes = retry_result[0] if retry_result else 15  # Default 15 minutes

            next_run = now + timedelta(minutes=retry_interval_minutes)

            # Quick WRITE to update job status
            with database.get_write_session_context() as db:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'FAILED',
                        error_message = :error_message,
                        last_run_finished_at = :now,
                        last_updated_at = :now,
                        next_run = :next_run,
                        retry_count = retry_count + 1
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                db.execute(update_query, {
                    'error_message': str(e),
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'now': now,
                    'next_run': next_run
                })
                # Commit happens automatically
                
        except Exception as update_error:
            logger.error(f"Failed to update job status to FAILED: {update_error}")
        
        raise


# Helper functions for modular Jira extraction

async def _initialize_jira_client(integration_id: int, tenant_id: int) -> tuple:
    """Initialize and validate Jira integration and client."""
    from app.core.database import get_database
    database = get_database()

    with database.get_read_session_context() as db:
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id
        ).first()

        if not integration:
            raise ValueError(f"Integration {integration_id} not found")

        if not integration.active:
            raise ValueError(f"Integration {integration.provider} is inactive - cannot execute extraction")

        # Create Jira client
        jira_client = JiraAPIClient.create_from_integration(integration)

        return integration, jira_client


async def store_raw_extraction_data(
    integration_id: int,
    tenant_id: int,
    entity_type: str,
    raw_data: Dict[str, Any]
) -> int:
    """Store raw extraction data and return the ID."""
    from app.core.database import get_database
    database = get_database()

    with database.get_write_session_context() as db:
        insert_query = text("""
            INSERT INTO raw_extraction_data (
                tenant_id, integration_id, type,
                raw_data, status, active, created_at
            ) VALUES (
                :tenant_id, :integration_id, :type,
                CAST(:raw_data AS jsonb), 'pending', TRUE, NOW()
            ) RETURNING id
        """)

        result = db.execute(insert_query, {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'type': entity_type,
            'raw_data': json.dumps(raw_data)
        })

        raw_data_id = result.fetchone()[0]
        # Commit happens automatically in context manager

        return raw_data_id


async def reset_job_countdown(tenant_id: int, job_id: int, message: str, job_start_time=None):
    """
    Update job status to FINISHED and set last_sync_date.

    Args:
        job_start_time: The time when the job started. Used to set last_sync_date for bounded incremental extraction.
                       If None, uses current time.
    """
    try:
        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        from datetime import timedelta
        import asyncio

        database = get_database()

        # First, READ job details from replica (fast)
        with database.get_read_session_context() as db:
            # Get the job details for logging
            job_query = text("""
                SELECT schedule_interval_minutes, last_run_started_at
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            job_result = db.execute(job_query, {
                'job_id': job_id,
                'tenant_id': tenant_id
            }).fetchone()

            if not job_result:
                logger.error(f"Job {job_id} not found for tenant {tenant_id}")
                return

            schedule_interval_minutes = job_result[0]
            last_run_started_at = job_result[1] if len(job_result) > 1 else None

        # Calculate next run time (no DB needed)
        now = DateTimeHelper.now_default()
        sync_time = job_start_time if job_start_time else now

        # ✅ FIX: Calculate next_run from when job STARTED, not when it FINISHED
        # This ensures countdown behavior is consistent regardless of job duration
        if last_run_started_at:
            next_run = last_run_started_at + timedelta(minutes=schedule_interval_minutes)
            logger.info(f"⏰ Calculating next_run from job START time (last_run_started_at)")
        else:
            # Fallback: if no start time, use current time
            next_run = now + timedelta(minutes=schedule_interval_minutes)
            logger.info(f"⏰ Calculating next_run from current time (no last_run_started_at)")

        logger.info(f"⏰ TIMEZONE CHECK: Current time (now) = {now}")
        logger.info(f"⏰ TIMEZONE CHECK: Job start time (last_run_started_at) = {last_run_started_at}")
        logger.info(f"⏰ TIMEZONE CHECK: Job sync time (sync_time) = {sync_time}")
        logger.info(f"⏰ TIMEZONE CHECK: Next run calculated = {next_run}")
        logger.info(f"⏰ TIMEZONE CHECK: Schedule interval = {schedule_interval_minutes} minutes")

        # Now WRITE to primary database (quick update, close immediately)
        with database.get_write_session_context() as db:
            # Step 1: Set status to FINISHED and update last_sync_date
            update_finished_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    last_run_finished_at = :now,
                    last_sync_date = :sync_time,
                    error_message = NULL,
                    retry_count = 0,
                    last_updated_at = :now
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_finished_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'now': now,
                'sync_time': sync_time
            })
            # Commit happens automatically

        logger.info(f"✅ Jira job marked as FINISHED")

        # Step 2: Send WebSocket status update to FINISHED
        from app.api.websocket_routes import get_websocket_manager
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_status_update(tenant_id, "Jira", "FINISHED", message)

        # Step 3: Send WebSocket completion update with success summary
        await websocket_manager.send_completion_update(tenant_id, "Jira", True, {
            "message": message,
            "schedule_interval_minutes": schedule_interval_minutes
        })

        logger.info(f"Job {job_id} completed successfully for tenant {tenant_id}: {message}")

        # Step 4: Wait a moment for frontend to process completion, then set to READY
        await asyncio.sleep(2)  # 2 second delay for frontend to show success

        # Quick WRITE to set READY status
        with database.get_write_session_context() as db:
            update_ready_query = text("""
                UPDATE etl_jobs
                SET status = 'READY',
                    next_run = :next_run,
                    last_updated_at = :now
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_ready_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'now': now,
                'next_run': next_run
            })
            # Commit happens automatically

        logger.info(f"✅ Jira job set to READY - next run scheduled for {next_run}")
        logger.info(f"Next run will be calculated as: last_updated_at + {schedule_interval_minutes} minutes")

        # Step 5: Send final status update to READY
        await websocket_manager.send_status_update(tenant_id, "Jira", "READY", f"Next run at {next_run}")

    except Exception as e:
        logger.error(f"Error updating job completion: {e}")


async def _extract_projects_and_issue_types(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    progress_tracker: JiraExtractionProgressTracker,
    step_index: int = 0  # Internal index (0-based for 4-step tracker)
) -> Dict[str, Any]:
    """Extract projects and issue types (Phase 2.1 / Step 1)."""

    # Step progress: Extract projects data (0.0 -> 0.3)
    await progress_tracker.update_step_progress(
        step_index, 0.0, f"Step 1: Fetching projects and issue types from {len(PROJECT_KEYS)} WEX projects"
    )

    # Extract projects with issue types using /project/search endpoint (not /createmeta)
    projects_list = jira_client.get_projects(
        project_keys=PROJECT_KEYS,
        expand="issueTypes"
    )

    if not projects_list:
        raise ValueError("No projects found in Jira project/search response")

    # Wrap in the expected structure for consistency with raw data storage
    projects_data = {'values': projects_list}

    # Step progress: Store raw data (0.3 -> 0.6)
    await progress_tracker.update_step_progress(
        step_index, 0.3, f"Step 1: Storing {len(projects_list)} projects with issue types"
    )

    raw_data_id = await store_raw_extraction_data(
        integration_id, tenant_id, "jira_project_search", projects_data
    )

    # Step progress: Process transformation (0.6 -> 1.0)
    await progress_tracker.update_step_progress(
        step_index, 0.6, f"Step 1: Processing projects and issue types data (raw_data_id={raw_data_id})"
    )

    # Process transformation directly using project/search data structure
    from app.workers.transform_worker import TransformWorker
    from app.etl.queue.queue_manager import QueueManager

    # Get the appropriate tier-based queue name for this tenant
    queue_manager = QueueManager()
    tier = queue_manager._get_tenant_tier(tenant_id)
    transform_queue = queue_manager.get_tier_queue_name(tier, 'transform')

    transform_worker = TransformWorker(queue_name=transform_queue)
    processed = transform_worker._process_jira_project_search(
        raw_data_id=raw_data_id,
        tenant_id=tenant_id,
        integration_id=integration_id
    )

    if not processed:
        raise ValueError("Failed to process projects transformation")

    # Count unique issue types (not n-n relationships)
    # Get unique issue types from database for accurate count
    from app.core.database import get_database
    from app.models.unified_models import Wit
    database = get_database()
    with database.get_read_session_context() as session:
        unique_issue_types_count = session.query(Wit).filter(
            Wit.tenant_id == tenant_id,
            Wit.integration_id == integration_id,
            Wit.active == True
        ).count()

    await progress_tracker.complete_step(
        step_index, f"Step 1 complete: {len(projects_list)} projects, {unique_issue_types_count} issue types"
    )

    return {
        "projects_count": len(projects_list),
        "issue_types_count": unique_issue_types_count,
        "raw_data_id": raw_data_id
    }


async def _extract_statuses_and_relationships(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    progress_tracker: JiraExtractionProgressTracker,
    step_index: int = 1  # Internal index (1 for 4-step tracker)
) -> Dict[str, Any]:
    """Extract statuses and project relationships (Phase 2.2 / Step 2)."""

    # Step progress: Get projects from database (0.0 -> 0.2)
    await progress_tracker.update_step_progress(
        step_index, 0.0, "Step 2: Fetching projects from database for status extraction"
    )

    # Get projects from database (like old ETL)
    # Use READ replica for fast query
    from app.core.database import get_database
    database = get_database()

    with database.get_read_session_context() as db:
        projects_query = text("""
            SELECT external_id, key, name
            FROM projects
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id AND active = true
        """)
        projects_result = db.execute(projects_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()

        if not projects_result:
            raise ValueError("No projects found in database. Please run projects extraction first.")

        project_keys = [row[1] for row in projects_result]  # Extract project keys
        logger.info(f"Found {len(project_keys)} projects for status extraction: {project_keys}")

    # Step progress: Extract project-specific statuses (0.0 -> 1.0)
    await progress_tracker.update_step_progress(
        step_index, 0.0, f"Step 2: Fetching project-specific statuses for {len(project_keys)} projects"
    )

    # Process each project's statuses individually (better granularity)
    total_statuses_processed = 0
    total_relationships_processed = 0

    for i, project_key in enumerate(project_keys):
        try:
            # Update progress for each project within step (0.0 -> 0.9)
            project_progress = (i / len(project_keys)) * 0.9
            await progress_tracker.update_step_progress(
                step_index, project_progress, f"Step 2: Processing project {i+1}/{len(project_keys)}: {project_key}"
            )

            # Call /rest/api/3/project/{project_key}/statuses for each project
            project_statuses_response = jira_client.get_project_statuses(project_key)

            if project_statuses_response:
                # Store raw data for this project individually
                project_raw_data = {
                    'project_key': project_key,
                    'statuses': project_statuses_response,
                    'extraction_metadata': {
                        'project_key': project_key,
                        'extracted_at': datetime.now(timezone.utc).isoformat(),
                        'api_endpoint': f'/rest/api/3/project/{project_key}/statuses',
                        'issue_types_count': len(project_statuses_response)
                    }
                }

                # Store raw data with unified type name (not per-project)
                raw_data_id = await store_raw_extraction_data(
                    integration_id, tenant_id,
                    "jira_project_statuses",  # Unified type for all project statuses
                    project_raw_data
                )

                # Process transformation for this project immediately
                from app.workers.transform_worker import TransformWorker
                from app.etl.queue.queue_manager import QueueManager

                # Get the appropriate tier-based queue name for this tenant
                queue_manager = QueueManager()
                tier = queue_manager._get_tenant_tier(tenant_id)
                transform_queue = queue_manager.get_tier_queue_name(tier, 'transform')

                transform_worker = TransformWorker(queue_name=transform_queue)
                processed = transform_worker._process_jira_statuses_and_project_relationships(
                    raw_data_id=raw_data_id,
                    tenant_id=tenant_id,
                    integration_id=integration_id
                )

                if processed:
                    # Count statuses and relationships for this project
                    project_statuses_count = 0
                    project_relationships_count = 0

                    for issuetype_data in project_statuses_response:
                        statuses_in_issuetype = len(issuetype_data.get('statuses', []))
                        project_statuses_count += statuses_in_issuetype
                        project_relationships_count += statuses_in_issuetype  # Each status creates a relationship

                    total_statuses_processed += project_statuses_count
                    total_relationships_processed += project_relationships_count

                    logger.info(f"Processed project {project_key}: {project_statuses_count} statuses, {project_relationships_count} relationships")
                else:
                    logger.warning(f"Failed to process transformation for project {project_key}")

        except Exception as e:
            logger.warning(f"Failed to process statuses for project {project_key}: {e}")
            continue

    # Step 2 complete (0.8 -> 1.0)
    # Get unique statuses count from database for accurate reporting
    from app.core.database import get_database
    from app.models.unified_models import Status
    database = get_database()
    with database.get_read_session_context() as session:
        unique_statuses_count = session.query(Status).filter(
            Status.tenant_id == tenant_id,
            Status.integration_id == integration_id,
            Status.active == True
        ).count()

    await progress_tracker.complete_step(
        step_index, f"Step 2 complete: {unique_statuses_count} statuses, {total_relationships_processed} project relationships across {len(project_keys)} projects"
    )

    return {
        "statuses_count": unique_statuses_count,
        "project_relationships_count": total_relationships_processed,
        "projects_processed": len(project_keys)
    }


async def _extract_issues_with_changelogs_for_complete_job(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    progress_tracker: 'JiraExtractionProgressTracker',
    job_id: int,
    job_start_time
) -> Dict[str, Any]:
    """
    Extract issues with changelogs for the complete job flow (Step 3).
    This is called as part of execute_complete_jira_extraction().

    Logic:
    - First run (last_sync_date is NULL): Fetch ALL issues (no date filter in JQL)
    - Subsequent runs: Fetch issues in bounded range: updated >= last_sync_date AND updated <= job_start_time

    Returns counts for progress tracking.
    """
    logger.info(f"Step 3: Extracting issues with changelogs for integration {integration_id}")

    # Get last_sync_date and integration settings from database
    # Use READ replica for fast query, close immediately
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.core.database import get_database

    database = get_database()
    with database.get_read_session_context() as db:
        # Get last_sync_date and integration settings in one query
        query = text("""
            SELECT ej.last_sync_date, i.settings
            FROM etl_jobs ej
            JOIN integrations i ON i.id = ej.integration_id
            WHERE ej.id = :job_id AND ej.tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise ValueError(f"Job {job_id} or integration {integration_id} not found")

        last_sync_date = result[0]
        integration_settings = result[1] or {}

        # Get project keys from integration settings
        project_keys = integration_settings.get('projects', PROJECT_KEYS)
        logger.info(f"Step 3: Using {len(project_keys)} projects from integration settings: {project_keys}")

    # Build JQL query with bounded date range and project filter
    project_filter = f"project in ({','.join(project_keys)})"

    if last_sync_date:
        # Incremental: fetch issues updated in bounded range [last_sync_date, job_start_time]
        jql = (
            f"{project_filter} AND "
            f"updated >= '{last_sync_date.strftime('%Y-%m-%d %H:%M')}' "
            f"AND updated <= '{job_start_time.strftime('%Y-%m-%d %H:%M')}' "
            f"ORDER BY updated ASC"
        )
        logger.info(f"Step 3: INCREMENTAL extraction - fetching issues updated between {last_sync_date} and {job_start_time}")
    else:
        # First run: fetch ALL issues up to job_start_time
        jql = f"{project_filter} AND updated <= '{job_start_time.strftime('%Y-%m-%d %H:%M')}' ORDER BY updated ASC"
        logger.info(f"Step 3: FIRST RUN - fetching ALL issues up to {job_start_time}")

    logger.info(f"Step 3: Using JQL query: {jql}")

    # Fetch issues with pagination - BATCH PROCESSING
    # Store and queue each batch immediately instead of accumulating in memory
    # NOTE: New Jira API uses nextPageToken for pagination (not startAt)
    next_page_token = None
    max_results = 100
    total_issues_processed = 0
    batches_stored = 0

    await progress_tracker.update_step_progress(
        2, 0.0, "Step 3: Starting issues extraction (fetching in batches of 100)"
    )

    from app.etl.queue.queue_manager import QueueManager
    queue_manager = QueueManager()

    while True:
        # Fetch one batch using nextPageToken
        logger.info(f"Step 3: Fetching batch #{batches_stored + 1} (nextPageToken={'present' if next_page_token else 'none'})...")

        try:
            response = jira_client.search_issues(
                jql=jql,
                next_page_token=next_page_token,
                max_results=max_results,
                fields=['*all'],
                expand=['changelog']
            )
        except Exception as fetch_error:
            logger.error(f"Step 3: Failed to fetch batch #{batches_stored + 1}: {fetch_error}")
            raise

        issues = response.get('issues', [])
        is_last = response.get('isLast', True)
        next_page_token = response.get('nextPageToken')

        # Check if we got any issues
        if not issues:
            if batches_stored == 0:
                logger.warning(f"Step 3: ⚠️ No issues found matching JQL query: {jql}")
            else:
                logger.info(f"Step 3: ✅ Reached end of results - fetched {total_issues_processed:,} total issues in {batches_stored} batches")
            break

        batch_size = len(issues)
        logger.info(f"Step 3: Fetched batch #{batches_stored + 1} with {batch_size} issues (isLast={is_last})")

        # Break batch into individual issue records for bulk insert
        # Use WRITE session, open only for insert, close immediately
        from sqlalchemy import text
        from datetime import datetime, timezone
        import time
        from app.core.database import get_database

        database = get_database()
        insert_start = time.time()

        with database.get_write_session_context() as db:
            now = datetime.now(timezone.utc)

            # Build VALUES clause and parameters for all issues
            values_clauses = []
            params = {
                'tenant_id': tenant_id,
                'integration_id': integration_id,
                'type': 'jira_issue',
                'status': 'pending',
                'created_at': now,
                'last_updated_at': now
            }

            for i, issue in enumerate(issues):
                # Create unique parameter name for each issue's raw_data
                param_name = f'raw_data_{i}'
                values_clauses.append(f"(:tenant_id, :integration_id, :type, :{param_name}, :status, :created_at, :last_updated_at)")
                params[param_name] = json.dumps(issue)

            # Build single INSERT query with all VALUES
            insert_query = text(f"""
                INSERT INTO raw_extraction_data (tenant_id, integration_id, type, raw_data, status, created_at, last_updated_at)
                VALUES {', '.join(values_clauses)}
                RETURNING id
            """)

            # Execute single bulk insert and collect all IDs
            result = db.execute(insert_query, params)
            raw_data_ids = [row[0] for row in result.fetchall()]
            # Commit happens automatically in context manager

        insert_time = (time.time() - insert_start) * 1000  # Convert to milliseconds
        batches_stored += 1
        logger.info(f"Step 3: ✅ Stored {len(raw_data_ids)} individual issues from batch #{batches_stored} in {insert_time:.0f}ms")

        # Bulk publish all issues to transform queue
        publish_start = time.time()
        published_count = 0
        failed_count = 0

        for raw_data_id in raw_data_ids:
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                data_type='jira_issue',  # Changed from 'jira_issues_changelogs'
                raw_data_id=raw_data_id
            )

            if success:
                published_count += 1
            else:
                failed_count += 1

        publish_time = (time.time() - publish_start) * 1000  # Convert to milliseconds

        if failed_count > 0:
            logger.warning(f"Step 3: ⚠️ Published {published_count}/{len(raw_data_ids)} issues to queue in {publish_time:.0f}ms ({failed_count} failed)")
        else:
            logger.info(f"Step 3: ✅ Published {published_count} issues to transform queue in {publish_time:.0f}ms")

        # Update progress
        total_issues_processed += batch_size

        # Update progress message (without knowing total, show incremental count)
        # Use logarithmic-style progress that approaches but never reaches 100%
        # This gives user feedback while extraction continues
        progress_within_step = min(0.95, 1.0 - (1.0 / (batches_stored + 1)))
        progress_message = f"Step 3: Extracting issues - {total_issues_processed:,} issues fetched ({batches_stored} batches)"

        await progress_tracker.update_step_progress(
            2, progress_within_step,
            progress_message
        )

        # Log progress every 10 batches
        if batches_stored % 10 == 0:
            logger.info(f"Step 3: 📊 Progress update - {batches_stored} batches complete ({total_issues_processed:,} issues)")

        # Check if this is the last page
        if is_last or not next_page_token:
            logger.info(f"Step 3: ✅ Reached last page - fetched {total_issues_processed:,} total issues in {batches_stored} batches")
            break

    # Final completion message
    if batches_stored > 0:
        logger.info(f"Step 3: ✅ COMPLETED - Stored and queued {batches_stored} batches ({total_issues_processed:,} total issues)")
        await progress_tracker.update_step_progress(
            2, 1.0, f"Step 3: Complete - {total_issues_processed:,} issues extracted in {batches_stored} batches"
        )
    else:
        logger.info(f"Step 3: ℹ️ No issues found to extract")
        await progress_tracker.update_step_progress(
            2, 1.0, "Step 3: Complete - No issues found"
        )

    return {
        'issues_count': total_issues_processed,
        'batches_count': batches_stored,
        'changelogs_count': 0  # Will be counted during transform processing
    }


async def _extract_dev_status_for_complete_job(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    progress_tracker: 'JiraExtractionProgressTracker',
    job_id: int,
    job_start_time
) -> Dict[str, Any]:
    """
    Extract dev status for the complete job flow (Step 4).
    This is called as part of execute_complete_jira_extraction().

    Logic:
    - First run (last_sync_date is NULL): Fetch dev status for ALL issues
    - Subsequent runs: Fetch dev status for issues in bounded range: updated >= last_sync_date AND updated <= job_start_time

    Returns counts for progress tracking.
    """
    logger.info(f"Step 4: Extracting dev status for integration {integration_id}")

    # Get issues with code changes from database
    # Use READ replica for query, close immediately
    await progress_tracker.update_step_progress(
        3, 0.1, "Step 4: Finding issues with code changes"
    )

    from sqlalchemy import text
    from app.core.database import get_database

    database = get_database()
    with database.get_read_session_context() as db:
        # Get last_sync_date to determine query scope
        sync_query = text("""
            SELECT last_sync_date
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        sync_result = db.execute(sync_query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()
        last_sync_date = sync_result[0] if sync_result else None

        # Build query with bounded date range - ONLY for issues with code_changed = True
        if last_sync_date:
            # Incremental: get issues updated in bounded range [last_sync_date, job_start_time] with code changes
            query = text("""
                SELECT key, external_id
                FROM work_items
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
                AND updated >= :last_sync_date AND updated <= :job_start_time
                AND code_changed = TRUE
                ORDER BY updated DESC
                LIMIT 1000
            """)
            issues = db.execute(query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'last_sync_date': last_sync_date,
                'job_start_time': job_start_time
            }).fetchall()
            logger.info(f"Step 4: INCREMENTAL - fetching dev status for issues with code changes updated between {last_sync_date} and {job_start_time}")
        else:
            # First run: get ALL issues with code changes up to job_start_time (with reasonable limit)
            query = text("""
                SELECT key, external_id
                FROM work_items
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
                AND updated <= :job_start_time
                AND code_changed = TRUE
                ORDER BY updated DESC
                LIMIT 5000
            """)
            issues = db.execute(query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'job_start_time': job_start_time
            }).fetchall()
            logger.info(f"Step 4: FIRST RUN - fetching dev status for ALL issues with code changes up to {job_start_time} (limit 5000)")

        issue_keys = [row[0] for row in issues]
        logger.info(f"Step 4: Found {len(issue_keys)} issues with code changes to check for dev status")
        # Context manager closes connection automatically

    if not issue_keys:
        logger.info("Step 4: ℹ️ No issues with code changes found - skipping dev status extraction")
        await progress_tracker.update_step_progress(
            3, 1.0, "Step 4: Complete - No issues with code changes"
        )
        return {'pr_links_count': 0}

    # Fetch dev status for each issue - BATCH PROCESSING
    # Store and queue every 50 issues to avoid memory buildup
    logger.info(f"Step 4: Starting dev status extraction for {len(issue_keys):,} issues with code changes")
    await progress_tracker.update_step_progress(
        3, 0.3, f"Step 4: Fetching dev status for {len(issue_keys):,} issues"
    )

    from app.etl.queue.queue_manager import QueueManager
    queue_manager = QueueManager()

    batch_size = 50
    current_batch = []
    batches_stored = 0
    total_pr_links = 0
    total_processed = 0
    total_batches_expected = ((len(issue_keys) + batch_size - 1) // batch_size)

    for i, issue_key in enumerate(issue_keys):
        try:
            dev_details = jira_client.get_issue_dev_details(issue_key)
            if dev_details:
                current_batch.append({
                    'issue_key': issue_key,
                    'dev_details': dev_details
                })

                # Count PR links in this item
                pr_count = len(dev_details.get('detail', [{}])[0].get('pullRequests', []))
                total_pr_links += pr_count

        except Exception as e:
            logger.warning(f"Step 4: ⚠️ Failed to fetch dev status for {issue_key}: {e}")

        total_processed += 1

        # Log progress every 50 issues
        if total_processed % 50 == 0:
            logger.info(f"Step 4: 📊 Processed {total_processed:,}/{len(issue_keys):,} issues ({total_processed/len(issue_keys)*100:.1f}%)")

        # Store and queue batch when it reaches batch_size or at the end
        if len(current_batch) >= batch_size or (i + 1) == len(issue_keys):
            if current_batch:
                # Store this batch - use WRITE session, close immediately
                from sqlalchemy import text
                from datetime import datetime, timezone
                from app.core.database import get_database

                database = get_database()
                with database.get_write_session_context() as db:
                    insert_query = text("""
                        INSERT INTO raw_extraction_data (tenant_id, integration_id, type, raw_data, status, created_at, last_updated_at)
                        VALUES (:tenant_id, :integration_id, :type, :raw_data, :status, :created_at, :last_updated_at)
                        RETURNING id
                    """)

                    result = db.execute(insert_query, {
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'type': 'jira_dev_status',
                        'raw_data': json.dumps({
                            'dev_status': current_batch,
                            'batch_info': {
                                'batch_number': batches_stored + 1,
                                'batch_size': len(current_batch),
                                'total_issues': len(issue_keys)
                            }
                        }),
                        'status': 'pending',
                        'created_at': datetime.now(timezone.utc),
                        'last_updated_at': datetime.now(timezone.utc)
                    })

                    raw_data_id = result.fetchone()[0]
                    # Commit happens automatically in context manager

                batches_stored += 1
                logger.info(f"Step 4: ✅ Stored dev status batch #{batches_stored}/{total_batches_expected} with raw_data_id={raw_data_id} ({len(current_batch)} issues)")

                # Publish this batch to transform queue
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    data_type='jira_dev_status',
                    raw_data_id=raw_data_id
                )

                if not success:
                    logger.error(f"Step 4: ❌ Failed to publish dev status batch #{batches_stored} to transform queue")
                else:
                    logger.info(f"Step 4: ✅ Published dev status batch #{batches_stored}/{total_batches_expected} to transform queue")

                # Clear batch
                current_batch = []

        # Update progress periodically (every 10 issues)
        if (i + 1) % 10 == 0:
            progress_within_step = 0.3 + (0.6 * ((i + 1) / len(issue_keys)))
            progress_message = f"Step 4: Extracting dev status - {total_processed:,}/{len(issue_keys):,} issues ({batches_stored} batches)"

            await progress_tracker.update_step_progress(
                3, progress_within_step,
                progress_message
            )

    logger.info(f"Step 4: ✅ COMPLETED - Stored and queued {batches_stored} batches ({total_processed:,} issues, {total_pr_links:,} PR links)")

    await progress_tracker.update_step_progress(
        3, 1.0, f"Step 4: Complete - {total_processed:,} issues processed, {total_pr_links:,} PR links found"
    )

    return {
        'pr_links_count': total_pr_links,
        'batches_count': batches_stored,
        'issues_processed': total_processed
    }


async def execute_issues_changelogs_dev_status_extraction(
    integration_id: int,
    tenant_id: int,
    job_id: int,
    incremental: bool = True
) -> Dict[str, Any]:
    """
    Execute complete issues, changelogs, and dev_status extraction.

    Flow:
    1. Fetch issues with changelogs using expand=changelog
    2. Store raw data in raw_extraction_data table
    3. Publish to transform queue with type 'jira_issues_changelogs'
    4. Transform worker processes and updates work_items and changelogs tables
    5. For issues with code_changed=true, fetch dev_status and process work_items_prs_links
    """
    logger.info(f"Starting issues extraction for integration {integration_id}, tenant {tenant_id}")

    progress_tracker = JiraExtractionProgressTracker(tenant_id, job_id)

    try:
        # Step 0: Initialize (0% -> 25%)
        await progress_tracker.update_step_progress(
            0, 0.0, "Initializing issues extraction"
        )

        # Get integration and create client
        integration, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        await progress_tracker.update_step_progress(
            0, 1.0, "Jira client initialized successfully"
        )

        # Step 1: Fetch issues with changelogs (25% -> 75%)
        await progress_tracker.update_step_progress(
            1, 0.0, "Fetching issues with changelogs from Jira"
        )

        issues_result = await _extract_issues_with_changelogs(
            jira_client, integration_id, tenant_id, incremental, progress_tracker
        )

        await progress_tracker.update_step_progress(
            1, 1.0, f"Fetched {issues_result['issues_count']} issues with changelogs"
        )

        # Step 2: Process dev_status for issues with code changes (75% -> 90%)
        await progress_tracker.update_step_progress(
            2, 0.0, "Processing development status for issues with code changes"
        )

        dev_status_result = await _extract_dev_status(
            jira_client, integration_id, tenant_id, issues_result.get('issues_with_code_changes', []), progress_tracker
        )

        await progress_tracker.update_step_progress(
            2, 1.0, f"Processed dev_status for {dev_status_result['dev_status_count']} issues"
        )

        # Step 3: Complete (90% -> 100%)
        await progress_tracker.update_step_progress(
            3, 0.5, "Finalizing extraction"
        )

        # Update job status to FINISHED
        from app.core.database import get_database
        database = get_database()

        with database.get_write_session_context() as db:
            update_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    last_run_completed_at = NOW(),
                    last_updated_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
            # Commit happens automatically

        await progress_tracker.update_step_progress(
            3, 1.0, "Issues extraction completed successfully"
        )

        # Send WebSocket completion update
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_status_update(
            tenant_id, "Jira", "FINISHED", "Issues extraction completed"
        )

        logger.info(f"Issues extraction completed for integration {integration_id}")

        return {
            "success": True,
            "issues_count": issues_result['issues_count'],
            "dev_status_count": dev_status_result['dev_status_count']
        }

    except Exception as e:
        logger.error(f"Issues extraction failed for integration {integration_id}: {e}")

        # Update job status to FINISHED with error
        from app.core.database import get_database
        database = get_database()

        with database.get_write_session_context() as db:
            update_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    last_run_completed_at = NOW(),
                    last_updated_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
            # Commit happens automatically

        # Send WebSocket error update
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_status_update(
            tenant_id, "Jira", "FINISHED", f"Issues extraction failed: {str(e)}"
        )

        raise


async def _extract_issues_with_changelogs(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    incremental: bool,
    progress_tracker: JiraExtractionProgressTracker
) -> Dict[str, Any]:
    """
    Extract issues with changelogs from Jira and store in raw_extraction_data.

    Returns:
        Dict containing:
        - issues_count: Number of issues extracted
        - issues_with_code_changes: List of issue keys with code_changed=true
    """
    from app.etl.raw_data import store_raw_extraction_data
    from app.etl.queue.queue_manager import get_queue_manager

    # Build JQL query for incremental extraction
    # For now, use a simple query - can be enhanced with last_sync_at logic later
    if incremental:
        # Get last 30 days of updates
        from datetime import datetime, timedelta, timezone
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        jira_date = thirty_days_ago.strftime('%Y-%m-%d %H:%M')
        jql = f"updated >= '{jira_date}' ORDER BY updated DESC"
    else:
        # Full extraction
        jql = "ORDER BY updated DESC"

    logger.info(f"Using JQL query: {jql}")

    # Define fields to fetch (including custom fields)
    fields = [
        'summary', 'description', 'status', 'issuetype', 'project',
        'created', 'updated', 'priority', 'resolution', 'labels',
        'assignee', 'parent', 'customfield_10016',  # Story points
        'customfield_10222',  # Acceptance criteria
        'customfield_10128',  # Team
    ]

    # Fetch issues with pagination
    all_issues = []
    issues_with_code_changes = []
    start_at = 0
    max_results = 100
    total_issues = None

    while True:
        result = jira_client.search_issues(
            jql=jql,
            start_at=start_at,
            max_results=max_results,
            fields=fields,
            expand=['changelog']
        )

        issues = result.get('issues', [])
        if not issues:
            break

        all_issues.extend(issues)

        # Track issues with code changes (code_changed field)
        for issue in issues:
            fields_data = issue.get('fields', {})
            # Check if issue has development information (indicates code changes)
            # This is a simplified check - actual implementation may vary
            if fields_data.get('customfield_10000'):  # Development field
                issues_with_code_changes.append(issue.get('key'))

        if total_issues is None:
            total_issues = result.get('total', 0)
            logger.info(f"Total issues to fetch: {total_issues}")

        start_at += len(issues)
        logger.info(f"Fetched {start_at}/{total_issues} issues")

        # Update progress
        if total_issues > 0:
            progress = start_at / total_issues
            await progress_tracker.update_step_progress(
                1, progress, f"Fetching issues: {start_at}/{total_issues}"
            )

        # Check if we've fetched all issues
        if start_at >= total_issues:
            break

    logger.info(f"Fetched {len(all_issues)} issues total")

    # Store raw data
    raw_data_id = store_raw_extraction_data(
        tenant_id=tenant_id,
        integration_id=integration_id,
        data_type='jira_issues_changelogs',
        raw_data={'issues': all_issues},
        source_info={'jql': jql, 'total_count': len(all_issues)}
    )

    logger.info(f"Stored raw issues data with ID: {raw_data_id}")

    # Publish to transform queue
    queue_manager = get_queue_manager()
    queue_manager.publish_transform_job(
        tenant_id=tenant_id,
        integration_id=integration_id,
        raw_data_id=raw_data_id,
        data_type='jira_issues_changelogs'
    )

    logger.info(f"Published issues to transform queue")

    return {
        'issues_count': len(all_issues),
        'issues_with_code_changes': issues_with_code_changes
    }


async def _extract_dev_status(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    issue_keys: List[str],
    progress_tracker: JiraExtractionProgressTracker
) -> Dict[str, Any]:
    """
    Extract dev_status for issues with code changes.

    Returns:
        Dict containing:
        - dev_status_count: Number of dev_status records extracted
    """
    from app.etl.raw_data import store_raw_extraction_data
    from app.etl.queue.queue_manager import get_queue_manager

    if not issue_keys:
        logger.info("No issues with code changes to process")
        return {'dev_status_count': 0}

    logger.info(f"Extracting dev_status for {len(issue_keys)} issues")

    # Get issue external IDs from database
    # Use READ replica for fast query
    from app.core.database import get_database
    database = get_database()

    with database.get_read_session_context() as db:
        query = text("""
            SELECT key, external_id
            FROM work_items
            WHERE tenant_id = :tenant_id AND integration_id = :integration_id
            AND key = ANY(:issue_keys)
        """)
        results = db.execute(query, {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'issue_keys': issue_keys
        }).fetchall()

        issue_map = {row[0]: row[1] for row in results}

    # Fetch dev_status for each issue
    dev_status_data = []
    processed_count = 0

    for issue_key in issue_keys:
        external_id = issue_map.get(issue_key)
        if not external_id:
            logger.warning(f"No external_id found for issue {issue_key}")
            continue

        try:
            dev_details = jira_client.get_issue_dev_details(external_id)
            if dev_details:
                dev_status_data.append({
                    'issue_key': issue_key,
                    'issue_external_id': external_id,
                    'dev_details': dev_details
                })
        except Exception as e:
            logger.warning(f"Failed to fetch dev_status for issue {issue_key}: {e}")

        processed_count += 1
        if processed_count % 10 == 0:
            progress = processed_count / len(issue_keys)
            await progress_tracker.update_step_progress(
                2, progress, f"Processing dev_status: {processed_count}/{len(issue_keys)}"
            )

    logger.info(f"Fetched dev_status for {len(dev_status_data)} issues")

    if dev_status_data:
        # Store raw data
        raw_data_id = store_raw_extraction_data(
            tenant_id=tenant_id,
            integration_id=integration_id,
            data_type='jira_dev_status',
            raw_data={'dev_status': dev_status_data},
            source_info={'total_count': len(dev_status_data)}
        )

        logger.info(f"Stored raw dev_status data with ID: {raw_data_id}")

        # Publish to transform queue
        queue_manager = get_queue_manager()
        queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=raw_data_id,
            data_type='jira_dev_status'
        )

        logger.info(f"Published dev_status to transform queue")

    return {'dev_status_count': len(dev_status_data)}


# FastAPI Router
router = APIRouter()


@router.post("/jira/extract/projects-and-issue-types/{integration_id}")
async def extract_projects_and_issue_types_endpoint(
    integration_id: int,
    background_tasks: BackgroundTasks,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Manually trigger complete Jira extraction (all 4 steps).

    This endpoint is called when user clicks "Run Now" button and executes
    the same function as the automatic scheduler: execute_complete_jira_extraction()

    Steps:
    1. Projects & Issue Types (0% -> 25%)
    2. Statuses & Project Relationships (25% -> 50%)
    3. Issues & Changelogs (50% -> 75%)
    4. Dev Status (75% -> 100%)

    This endpoint:
    1. Validates the integration exists and is active
    2. Finds the corresponding ETL job
    3. Sets job status to RUNNING
    4. Triggers background extraction task for all 4 steps
    5. Returns success response
    """
    try:
        # Validate integration exists and is active
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        if not integration.active:
            raise HTTPException(status_code=400, detail="Integration is inactive")

        # Find the Jira job for this integration
        job_query = text("""
            SELECT id, job_name, status, active
            FROM etl_jobs
            WHERE tenant_id = :tenant_id AND integration_id = :integration_id
            AND job_name = 'Jira'
        """)

        result = db.execute(job_query, {
            'tenant_id': tenant_id,
            'integration_id': integration_id
        }).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Jira job not found")

        job_id, job_name, status, active = result

        if not active:
            raise HTTPException(status_code=400, detail=f"Job {job_name} is inactive")

        if status == 'RUNNING':
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        # Set job to RUNNING
        update_query = text("""
            UPDATE etl_jobs
            SET status = 'RUNNING',
                last_run_started_at = NOW(),
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
        db.commit()

        # Send WebSocket status update
        from app.api.websocket_routes import get_websocket_manager
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_status_update(tenant_id, "Jira", "RUNNING", "Job started")

        # Log before adding background task
        logger.info(f"📋 Adding background task: execute_complete_jira_extraction(integration_id={integration_id}, tenant_id={tenant_id}, job_id={job_id})")

        # Add background task for complete extraction (same as automatic scheduler)
        background_tasks.add_task(
            execute_complete_jira_extraction,
            integration_id,
            tenant_id,
            job_id
        )

        logger.info(f"✅ Background task added successfully")

        return {
            "success": True,
            "message": f"Complete Jira extraction started for {job_name} (4 steps)",
            "job_id": job_id,
            "integration_id": integration_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting complete Jira extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jira/extract/issues-changelogs-dev-status/{integration_id}")
async def extract_issues_changelogs_dev_status_endpoint(
    integration_id: int,
    background_tasks: BackgroundTasks,
    tenant_id: int = Query(..., description="Tenant ID"),
    incremental: bool = Query(True, description="Incremental extraction (last 30 days)"),
    db: Session = Depends(get_db_session)
):
    """
    Manually trigger issues, changelogs, and dev_status extraction.

    This endpoint:
    1. Validates the integration exists and is active
    2. Finds the corresponding ETL job
    3. Sets job status to RUNNING
    4. Triggers background extraction task for issues, changelogs, and dev_status
    5. Returns success response
    """
    try:
        # Validate integration exists and is active
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        if not integration.active:
            raise HTTPException(status_code=400, detail="Integration is inactive")

        # Find the Jira job for this integration
        job_query = text("""
            SELECT id, job_name, status, active
            FROM etl_jobs
            WHERE tenant_id = :tenant_id AND integration_id = :integration_id
            AND job_name = 'Jira'
        """)

        result = db.execute(job_query, {
            'tenant_id': tenant_id,
            'integration_id': integration_id
        }).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Jira job not found")

        job_id, job_name, status, active = result

        if not active:
            raise HTTPException(status_code=400, detail=f"Job {job_name} is inactive")

        if status == 'RUNNING':
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        # Set job to RUNNING
        update_query = text("""
            UPDATE etl_jobs
            SET status = 'RUNNING',
                last_run_started_at = NOW(),
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
        db.commit()

        # Send WebSocket status update
        from app.api.websocket_routes import get_websocket_manager
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_status_update(tenant_id, "Jira", "RUNNING", "Issues extraction started")

        # Add background task for issues extraction
        background_tasks.add_task(
            execute_issues_changelogs_dev_status_extraction,
            integration_id,
            tenant_id,
            job_id,
            incremental
        )

        return {
            "success": True,
            "message": f"Issues, changelogs, and dev_status extraction started for {job_name}",
            "job_id": job_id,
            "integration_id": integration_id,
            "incremental": incremental
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting issues extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
