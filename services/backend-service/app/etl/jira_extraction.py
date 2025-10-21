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

from app.core.database import get_db_session, get_read_session
from app.core.logging_config import get_logger
from app.etl.jira_client import JiraAPIClient
from app.models.unified_models import Integration

logger = get_logger(__name__)







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



    try:
        # Step 1: Projects & Issue Types (0% -> 33%)
        logger.info("=" * 80)
        logger.info("STARTING STEP 1: Projects & Issue Types Extraction")
        logger.info("=" * 80)

        # Get integration and create client
        integration, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        projects_result = await _extract_projects_and_issue_types(
            jira_client, integration_id, tenant_id
        )

        logger.info(f"✅ Step 1 completed: {projects_result['projects_count']} projects, {projects_result['issue_types_count']} issue types")

        # Step 2: Statuses & Relationships (33% -> 66%)
        logger.info("=" * 80)
        logger.info("STARTING STEP 2: Statuses & Project Relationships Extraction")
        logger.info("=" * 80)

        statuses_result = await _extract_statuses_and_relationships(
            jira_client, integration_id, tenant_id
        )

        logger.info(f"✅ Step 2 completed: {statuses_result['statuses_count']} statuses, {statuses_result['project_relationships_count']} relationships")

        # Step 3: Issues & Changelogs (66% -> 100%)
        # Note: Dev status extraction happens in background via extraction_queue
        logger.info("=" * 80)
        logger.info("STARTING STEP 3: Issues & Changelogs Extraction")
        logger.info("=" * 80)
        logger.info(f"🔍 DEBUG: Job status should be RUNNING during Step 3")



        try:
            logger.info(f"🔍 DEBUG: About to call _extract_issues_with_changelogs_for_complete_job")
            issues_result = await _extract_issues_with_changelogs_for_complete_job(
                jira_client, integration_id, tenant_id, job_id, job_start_time
            )
            logger.info(f"✅ Step 3 completed: {issues_result}")
            logger.info(f"🔍 DEBUG: Returned from _extract_issues_with_changelogs_for_complete_job - job should still be RUNNING")
        except Exception as issues_error:
            logger.error(f"❌ Step 3 (Issues extraction) failed: {issues_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise


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



    try:
        # Step 0: Projects & Issue Types (0% -> 50%)
        # Get integration and create client
        integration, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        projects_result = await _extract_projects_and_issue_types(
            jira_client, integration_id, tenant_id
        )

        # Step 1: Statuses & Relationships (50% -> 100%)
        statuses_result = await _extract_statuses_and_relationships(
            jira_client, integration_id, tenant_id
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
                SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('FINISHED'::text)),
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
        logger.info(f"Job {job_id} completed successfully for tenant {tenant_id}: {message}")

        # Step 4: Wait a moment for frontend to process completion, then set to READY
        await asyncio.sleep(2)  # 2 second delay for frontend to show success

        # Quick WRITE to set READY status
        with database.get_write_session_context() as db:
            update_ready_query = text("""
                UPDATE etl_jobs
                SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('READY'::text)),
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

    except Exception as e:
        logger.error(f"Error updating job completion: {e}")


async def _extract_projects_and_issue_types(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    job_id: int = None  # ETL job ID for tracking
) -> Dict[str, Any]:
    """Extract projects and issue types (Phase 2.1 / Step 1)."""

    # Set last_run_started_at for this ETL job
    from datetime import datetime
    job_start_time = datetime.now()

    if job_id:
        from app.core.database import get_database
        from sqlalchemy import text
        database = get_database()
        with database.get_write_session_context() as db:
            update_query = text("""
                UPDATE etl_jobs
                SET last_run_started_at = :job_start_time,
                    last_updated_at = :job_start_time
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'job_start_time': job_start_time
            })
            logger.info(f"✅ Set last_run_started_at to {job_start_time} for job {job_id}")

    # Get integration settings to determine which projects to extract
    from sqlalchemy import text
    with get_read_session() as db:
        result = db.execute(text("""
            SELECT id, settings
            FROM integrations
            WHERE id = :integration_id AND tenant_id = :tenant_id
        """), {"integration_id": integration_id, "tenant_id": tenant_id}).fetchone()

        if not result:
            raise ValueError(f"Integration {integration_id} not found for tenant {tenant_id}")

        integration_settings = result[1] or {}
        project_keys = integration_settings.get('projects', [])

        if not project_keys:
            raise ValueError("No projects configured in integration settings. Please configure projects in the integration settings.")

        logger.info(f"Step 1: Using {len(project_keys)} configured projects: {project_keys}")



    # Extract configured projects with issue types using /project/search endpoint
    # Filter by the projects configured in integration settings
    projects_list = jira_client.get_projects(
        project_keys=project_keys,
        expand="issueTypes"
    )

    if not projects_list:
        raise ValueError("No projects found in Jira project/search response")

    # Wrap in the expected structure for consistency with raw data storage
    projects_data = {'values': projects_list}



    raw_data_id = await store_raw_extraction_data(
        integration_id, tenant_id, "jira_project_search", projects_data
    )



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



    # Publish to transform queue with first_item=true and job_start_time
    if job_id:
        from app.etl.queue.queue_manager import get_queue_manager
        queue_manager = get_queue_manager()

        # Get integration for provider name
        from app.core.database import get_database
        from app.models.unified_models import Integration
        database = get_database()
        with database.get_read_session_context() as db:
            integration = db.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == tenant_id
            ).first()
            provider_name = integration.provider if integration else 'Jira'

        success = queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=raw_data_id,
            data_type='jira_projects_and_issue_types',  # 🔧 Use correct step name for UI
            job_id=job_id,
            provider=provider_name,
            last_sync_date=job_start_time.isoformat(),
            first_item=True,  # ✅ Single message (first)
            last_item=True   # ✅ Single message (last)
        )

        if success:
            logger.info(f"✅ Published projects and issue types to transform queue with first_item=true")
        else:
            logger.error(f"❌ Failed to publish projects and issue types to transform queue")

    return {
        "success": True,
        "projects_count": len(projects_list),
        "issue_types_count": unique_issue_types_count,
        "raw_data_id": raw_data_id,
        "job_start_time": job_start_time.isoformat() if job_id else None
    }


async def _extract_statuses_and_relationships(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    job_id: int = None
) -> Dict[str, Any]:
    """Extract statuses and project relationships (Phase 2.2 / Step 2)."""

    logger.info(f"🔍 [DEBUG] Starting _extract_statuses_and_relationships for tenant {tenant_id}, integration {integration_id}")



    # Get projects from database (like old ETL)
    # Use READ replica for fast query
    from app.core.database import get_database
    from sqlalchemy import text
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
            logger.error(f"🔍 [DEBUG] No projects found in database for tenant {tenant_id}, integration {integration_id}")
            raise ValueError("No projects found in database. Please run projects extraction first.")

        project_keys = [row[1] for row in projects_result]  # Extract project keys
        logger.info(f"🔍 [DEBUG] Found {len(project_keys)} projects for status extraction: {project_keys}")



    # Process each project's statuses individually (better granularity)
    total_statuses_processed = 0
    total_relationships_processed = 0

    for i, project_key in enumerate(project_keys):
        try:


            # Call /rest/api/3/project/{project_key}/statuses for each project
            logger.info(f"🔍 [DEBUG] Calling get_project_statuses for project {project_key}")
            project_statuses_response = jira_client.get_project_statuses(project_key)
            logger.info(f"🔍 [DEBUG] get_project_statuses returned: {len(project_statuses_response) if project_statuses_response else 0} issue types for project {project_key}")

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

                # Queue transformation using proper queue architecture
                from app.etl.queue.queue_manager import QueueManager

                queue_manager = QueueManager()
                logger.info(f"🔍 [DEBUG] About to queue transform job for project {project_key}, raw_data_id={raw_data_id}")

                # Set flags for proper queue processing
                first_item = (i == 0)
                last_item = (i == len(project_keys) - 1)

                queued = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=raw_data_id,
                    data_type='jira_statuses_and_relationships',  # 🔧 Use correct step name for UI
                    job_id=job_id,
                    provider='jira',
                    first_item=first_item,
                    last_item=last_item
                )

                logger.info(f"🔍 [DEBUG] Transform job queued: {queued} for project {project_key}")

                if queued:
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
            logger.error(f"❌ [DEBUG] Exception in project loop for {project_key}: {e}")
            import traceback
            logger.error(f"Project loop traceback: {traceback.format_exc()}")
            continue

    # Step 2 complete (0.8 -> 1.0)
    # Get unique statuses count from database for accurate reporting
    logger.info(f"🔍 [DEBUG] Getting unique statuses count from database for tenant {tenant_id}, integration {integration_id}")
    from app.core.database import get_database
    from app.models.unified_models import Status
    database = get_database()
    with database.get_read_session_context() as session:
        unique_statuses_count = session.query(Status).filter(
            Status.tenant_id == tenant_id,
            Status.integration_id == integration_id,
            Status.active == True
        ).count()
        logger.info(f"🔍 [DEBUG] Found {unique_statuses_count} unique statuses in database")



    logger.info(f"🔍 [DEBUG] _extract_statuses_and_relationships completed successfully - returning success=True")

    return {
        "success": True,
        "statuses_count": unique_statuses_count,
        "project_relationships_count": total_relationships_processed,
        "projects_processed": len(project_keys)
    }


async def _extract_issues_with_changelogs_for_complete_job(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
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

        # Get project keys from integration settings or database
        project_keys = integration_settings.get('projects')

        if not project_keys:
            # Fallback: get project keys from database
            logger.info("No projects in integration settings, fetching from database...")
            from sqlalchemy import text
            with get_read_session() as db:
                projects_result = db.execute(text("""
                    SELECT DISTINCT external_id, key
                    FROM jira_projects
                    WHERE tenant_id = :tenant_id AND integration_id = :integration_id
                """), {"tenant_id": tenant_id, "integration_id": integration_id}).fetchall()

                if not projects_result:
                    raise ValueError("No projects found in database or integration settings. Please run projects extraction first.")

                project_keys = [row[1] for row in projects_result]  # Extract project keys

        logger.info(f"Step 3: Using {len(project_keys)} projects: {project_keys}")

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
                raw_data_id=raw_data_id,
                data_type='jira_issues_with_changelogs',  # 🔧 Use correct step name for UI
                provider='jira'
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
    else:
        logger.info(f"Step 3: ℹ️ No issues found to extract")

    return {
        'success': True,
        'issues_count': total_issues_processed,
        'batches_count': batches_stored,
        'changelogs_count': 0  # Will be counted during transform processing
    }


async def _extract_dev_status_for_complete_job(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
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

        return {'success': True, 'pr_links_count': 0}

    # Fetch dev status for each issue - BATCH PROCESSING
    # Store and queue every 50 issues to avoid memory buildup
    logger.info(f"Step 4: Starting dev status extraction for {len(issue_keys):,} issues with code changes")


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
                    raw_data_id=raw_data_id,
                    data_type='jira_dev_status',
                    provider='jira'
                )

                if not success:
                    logger.error(f"Step 4: ❌ Failed to publish dev status batch #{batches_stored} to transform queue")
                else:
                    logger.info(f"Step 4: ✅ Published dev status batch #{batches_stored}/{total_batches_expected} to transform queue")

                # Clear batch
                current_batch = []





    logger.info(f"Step 4: ✅ COMPLETED - Stored and queued {batches_stored} batches ({total_processed:,} issues, {total_pr_links:,} PR links)")



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

    try:
        # Get integration and create client
        _, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        issues_result = await _extract_issues_with_changelogs(
            jira_client, integration_id, tenant_id, incremental, job_id
        )

        dev_status_result = await _extract_dev_status(
            jira_client, integration_id, tenant_id, issues_result.get('issues_with_code_changes', [])
        )

        # Update job status to FINISHED
        from app.core.database import get_database
        database = get_database()

        with database.get_write_session_context() as db:
            update_query = text("""
                UPDATE etl_jobs
                SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('FINISHED'::text)),
                    last_run_completed_at = NOW(),
                    last_updated_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
            # Commit happens automatically





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



        raise


async def _extract_issues_with_changelogs(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    incremental: bool,
    job_id: int = None
) -> Dict[str, Any]:
    """
    Extract issues with changelogs from Jira and store in raw_extraction_data.

    Returns:
        Dict containing:
        - issues_count: Number of issues extracted
        - issues_with_code_changes: List of issue keys with code_changed=true
    """

    from app.etl.queue.queue_manager import get_queue_manager
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.core.database import get_database
    import json

    # Get last_sync_date and integration settings from database
    database = get_database()
    with database.get_read_session_context() as db:
        # Get last_sync_date and integration settings in one query
        query = text("""
            SELECT ej.last_sync_date, i.settings
            FROM etl_jobs ej
            JOIN integrations i ON i.id = ej.integration_id
            WHERE ej.integration_id = :integration_id AND ej.tenant_id = :tenant_id
        """)
        result = db.execute(query, {'integration_id': integration_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise ValueError(f"Integration {integration_id} or ETL job not found for tenant {tenant_id}")

        last_sync_date, settings_json = result

    # Parse integration settings
    settings = settings_json if isinstance(settings_json, dict) else json.loads(settings_json or '{}')
    projects = settings.get('projects', [])

    logger.info(f"[DEBUG] Last sync date: {last_sync_date}")
    logger.info(f"[DEBUG] Integration projects: {projects}")

    # Build JQL query with proper date and project filtering
    jql_parts = []

    # Add project filter if projects are specified
    if projects:
        if len(projects) == 1:
            jql_parts.append(f"project = {projects[0]}")
        else:
            project_list = ", ".join(projects)
            jql_parts.append(f"project in ({project_list})")

    # Add date filter for incremental extraction
    if incremental and last_sync_date:
        # Use last_sync_date for incremental extraction
        jira_date = last_sync_date.strftime('%Y-%m-%d %H:%M')
        jql_parts.append(f"updated >= '{jira_date}'")
    elif incremental:
        # Fallback to 30 days if no last_sync_date
        from datetime import timedelta
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        jira_date = thirty_days_ago.strftime('%Y-%m-%d %H:%M')
        jql_parts.append(f"updated >= '{jira_date}'")

    # Combine JQL parts
    if jql_parts:
        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    else:
        jql = "ORDER BY updated DESC"

    logger.info(f"[DEBUG] Using JQL query: {jql}")

    # Use *all fields - explicitly request all fields
    fields = ['*all']  # This will fetch all fields

    # Fetch issues with pagination using next_page_token
    all_issues = []
    issues_with_code_changes = []
    next_page_token = None
    max_results = 100
    total_issues = None

    while True:
        result = jira_client.search_issues(
            jql=jql,
            next_page_token=next_page_token,
            max_results=max_results,
            fields=fields,  # None = fetch all fields (*all)
            expand=['changelog']
        )

        issues = result.get('issues', [])
        if not issues:
            break

        all_issues.extend(issues)

        # Track issues with code changes (development field)
        # Note: This is just for tracking - actual dev_status queueing happens in transform worker
        # using proper custom_field_mappings
        for issue in issues:
            fields_data = issue.get('fields', {})
            # Check if issue has development information (indicates code changes)
            # Using environment variable for development field ID (fallback to common default)
            import os
            development_field_id = os.getenv('JIRA_DEVELOPMENT_FIELD_ID', 'customfield_10000')
            if fields_data.get(development_field_id):
                issues_with_code_changes.append(issue.get('key'))

        if total_issues is None:
            total_issues = result.get('total', 0)
            logger.info(f"[DEBUG] Total issues to fetch: {total_issues}")

        current_count = len(all_issues)
        logger.info(f"[DEBUG] Fetched {current_count}/{total_issues} issues")



        # Check if we have more pages using the new token-based pagination
        next_page_token = result.get('nextPageToken')
        is_last = result.get('isLast', True)

        if is_last or not next_page_token:
            break

    logger.info(f"[DEBUG] Fetched {len(all_issues)} issues total")

    # Get integration to determine provider name
    with get_read_session() as session:
        integration = session.query(Integration).filter(Integration.id == integration_id).first()
        provider_name = integration.provider if integration else "Unknown"

    # Convert last_sync_date to string for JSON serialization
    last_sync_date_str = last_sync_date.isoformat() if last_sync_date else None

    # Store each issue individually and queue to transform
    queue_manager = get_queue_manager()
    stored_count = 0
    published_count = 0

    # 🎯 HANDLE CASE: No issues found - send completion message to transform
    if not all_issues:
        logger.info(f"[DEBUG] No issues found - sending completion message to transform queue")

        # Send completion message with raw_data_id=None to signal job completion
        success = queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=None,  # 🔧 None signals completion message
            data_type='jira_issues_with_changelogs',
            job_id=job_id,
            provider=provider_name,
            last_sync_date=last_sync_date_str,
            first_item=True,
            last_item=True,
            last_issue_changelog_item=True,
            last_job_item=True  # 🎯 Complete the job since no data to process
        )

        if success:
            logger.info(f"✅ Sent completion message to transform queue (no issues found)")
            published_count = 1
        else:
            logger.error(f"❌ Failed to send completion message to transform queue")

        return {
            'success': True,
            'issues_count': 0,
            'issues_with_code_changes': [],
            'dev_status_queued': 0
        }

    for i, issue in enumerate(all_issues):
        # Store individual issue as raw data
        raw_data_id = await store_raw_extraction_data(
            integration_id=integration_id,
            tenant_id=tenant_id,
            entity_type='jira_single_issue_changelog',
            raw_data={'issue': issue}
        )
        stored_count += 1

        # Set flags for proper queue processing
        first_item = (i == 0)
        last_item = (i == len(all_issues) - 1)

        # 🎯 CRITICAL: Issues should NEVER complete the job when there are development issues
        # If issues have development field, dev_status extraction will complete the job
        # If NO issues have development field, the last issue should complete the job
        has_development_issues = len(issues_with_code_changes) > 0
        last_job_item = last_item and not has_development_issues

        # Publish individual issue to transform queue
        success = queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=raw_data_id,
            data_type='jira_issues_with_changelogs',  # 🔧 Use correct step name for UI
            job_id=job_id,
            provider=provider_name,
            last_sync_date=last_sync_date_str,
            first_item=first_item,
            last_item=last_item,
            last_issue_changelog_item=last_item,  # Keep for backward compatibility
            last_job_item=last_job_item  # 🎯 Complete job if no dev_status needed
        )

        if success:
            published_count += 1
            if last_job_item:
                logger.info(f"✅ Issue {issue.get('key')} queued with last_job_item=True (will complete job)")
            else:
                logger.debug(f"📝 Issue {issue.get('key')} queued (first={first_item}, last={last_item})")

    logger.info(f"[DEBUG] Stored {stored_count} individual issues and published {published_count} to transform queue")

    # Log the decision about job completion
    if issues_with_code_changes:
        logger.info(f"[DEBUG] Found {len(issues_with_code_changes)} issues with development field - job completion will be handled by dev_status extraction")
    else:
        logger.info(f"[DEBUG] No issues with development field - job completion handled by last issue transform")

    # 🎯 NEW ARCHITECTURE: Queue dev_status extractions for issues with development field
    # This is where we have full context to set proper first_item/last_item/last_job_item flags
    dev_status_queued = 0

    if issues_with_code_changes:
        logger.info(f"[DEBUG] Queueing {len(issues_with_code_changes)} issues for dev_status extraction")

        for i, issue_key in enumerate(issues_with_code_changes):
            # Find the issue data by key
            issue_data = None
            for issue in all_issues:
                if issue.get('key') == issue_key:
                    issue_data = issue
                    break

            if not issue_data:
                logger.warning(f"Could not find issue data for {issue_key}")
                continue

            # Set flags for dev_status extraction
            first_item = (i == 0)
            last_item = (i == len(issues_with_code_changes) - 1)
            last_job_item = last_item  # 🎯 Mark the final dev_status as the job completion trigger

            # Queue dev_status extraction
            success = queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                extraction_type='jira_dev_status_fetch',
                extraction_data={
                    'issue_id': issue_data.get('id'),
                    'issue_key': issue_data.get('key')
                },
                job_id=job_id,
                provider=provider_name,
                last_sync_date=last_sync_date_str,
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_job_item
            )

            if success:
                dev_status_queued += 1
                logger.debug(f"✅ Queued dev_status extraction for {issue_key} (first={first_item}, last={last_item}, job_end={last_job_item})")
            else:
                logger.error(f"❌ Failed to queue dev_status extraction for {issue_key}")

    logger.info(f"[DEBUG] Queued {dev_status_queued} dev_status extractions")

    return {
        'success': True,
        'issues_count': len(all_issues),
        'issues_with_code_changes': issues_with_code_changes,
        'dev_status_queued': dev_status_queued
    }


async def _extract_dev_status(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    issue_keys: List[str]
) -> Dict[str, Any]:
    """
    Extract dev_status for issues with code changes.

    Returns:
        Dict containing:
        - dev_status_count: Number of dev_status records extracted
    """

    from app.etl.queue.queue_manager import get_queue_manager

    if not issue_keys:
        logger.info("No issues with code changes to process")
        return {'success': True, 'dev_status_count': 0}

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

    logger.info(f"Fetched dev_status for {len(dev_status_data)} issues")

    if dev_status_data:
        # Store raw data
        raw_data_id = await store_raw_extraction_data(
            integration_id=integration_id,
            tenant_id=tenant_id,
            entity_type='jira_dev_status',
            raw_data={'dev_status': dev_status_data}
        )

        logger.info(f"Stored raw dev_status data with ID: {raw_data_id}")

        # Publish to transform queue
        queue_manager = get_queue_manager()
        queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=raw_data_id,
            data_type='jira_dev_status',
            provider='jira'
        )

        logger.info(f"Published dev_status to transform queue")

    return {'success': True, 'dev_status_count': len(dev_status_data)}


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
            SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('RUNNING'::text)),
                last_run_started_at = NOW(),
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
        db.commit()



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
            SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('RUNNING'::text)),
                last_run_started_at = NOW(),
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
        db.commit()



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
