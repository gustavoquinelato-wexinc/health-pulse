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

    # Define the 4 steps for Jira extraction
    TOTAL_STEPS = 4

    def __init__(self, tenant_id: int, job_id: int):
        self.tenant_id = tenant_id
        self.job_id = job_id
        self.websocket_manager = get_websocket_manager()

    async def update_step_progress(self, step_index: int, step_progress: float, message: str):
        """Update progress using step-based system (like old ETL service)."""
        try:
            # Calculate overall percentage using step-based system
            step_percentage = 100.0 / self.TOTAL_STEPS
            step_start = step_index * step_percentage
            overall_percentage = step_start + (step_progress * step_percentage)

            # Log progress (no database update - progress is tracked in UI only)
            logger.info(f"[JIRA EXTRACTION] Step {step_index + 1}/{self.TOTAL_STEPS} - {overall_percentage:.1f}% - {message}")

            # Send WebSocket update
            await self.websocket_manager.send_progress_update(
                self.tenant_id, "Jira", overall_percentage, message
            )

        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

    async def complete_step(self, step_index: int, message: str):
        """Mark a step as completed."""
        await self.update_step_progress(step_index, 1.0, message)


async def execute_projects_and_issue_types_extraction(
    integration_id: int,
    tenant_id: int,
    job_id: int
) -> Dict[str, Any]:
    """
    Execute complete Jira extraction with all phases.

    Combined Flow (Phase 2.1 + 2.2):
    1. Projects & Issue Types (40% total)
    2. Statuses & Project Relationships (40% total)
    3. Future phases can be added here (remaining 20%)
    """
    logger.info(f"🚀 ETL JOB STARTED: 'Jira' (ID: {job_id}) - Beginning execution")

    progress_tracker = JiraExtractionProgressTracker(tenant_id, job_id)

    try:
        # Step 0: Initialize (0% -> 25%)
        await progress_tracker.update_step_progress(
            0, 0.0, "Validating integration and setting up Jira client"
        )

        # Get integration and create client
        integration, jira_client = await _initialize_jira_client(integration_id, tenant_id)

        await progress_tracker.update_step_progress(
            0, 1.0, "Jira client initialized successfully"
        )

        # Step 1: Execute Phase 2.1 - Projects & Issue Types (25% -> 50%)
        await progress_tracker.update_step_progress(
            1, 0.0, "Starting projects and issue types extraction"
        )

        projects_result = await _extract_projects_and_issue_types(
            jira_client, integration_id, tenant_id, progress_tracker
        )

        # Step 2: Execute Phase 2.2 - Statuses & Relationships (50% -> 75%)
        await progress_tracker.update_step_progress(
            2, 0.0, "Starting statuses and project relationships extraction"
        )

        statuses_result = await _extract_statuses_and_relationships(
            jira_client, integration_id, tenant_id, progress_tracker
        )

        # Step 3: Complete (75% -> 100%)
        await progress_tracker.update_step_progress(
            3, 1.0, f"Successfully completed Jira extraction: {projects_result['projects_count']} projects, {projects_result['issue_types_count']} issue types, {statuses_result['statuses_count']} statuses"
        )
        
        # Update job status to FINISHED
        await reset_job_countdown(tenant_id, job_id, "Complete Jira extraction finished successfully")

        logger.info(f"Complete Jira extraction completed for integration {integration_id}")
        logger.info(f"🏁 ETL JOB FINISHED: 'Jira' (ID: {job_id}) - Execution completed successfully")

        return {
            "success": True,
            "projects_count": projects_result['projects_count'],
            "issue_types_count": projects_result['issue_types_count'],
            "statuses_count": statuses_result['statuses_count'],
            "project_relationships_count": statuses_result['project_relationships_count']
        }
        
    except Exception as e:
        logger.error(f"Complete Jira extraction failed for integration {integration_id}: {e}")
        logger.error(f"💥 ETL JOB FAILED: 'Jira' (ID: {job_id}) - Execution failed with error: {e}")

        # Update job status to FAILED
        try:
            await progress_tracker.websocket_client.send_progress_update(
                "Jira", 100.0, f"[ERROR] Jira extraction failed: {str(e)}"
            )
            
            db = next(get_db_session())
            try:
                from app.core.utils import DateTimeHelper
                from datetime import timedelta
                now = DateTimeHelper.now_default()

                # Get retry interval to calculate next retry time
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
                db.commit()
                
            finally:
                db.close()
                
        except Exception as update_error:
            logger.error(f"Failed to update job status to FAILED: {update_error}")
        
        raise


# Helper functions for modular Jira extraction

async def _initialize_jira_client(integration_id: int, tenant_id: int) -> tuple:
    """Initialize and validate Jira integration and client."""
    db = next(get_db_session())
    try:
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
        
    finally:
        db.close()


async def store_raw_extraction_data(
    integration_id: int,
    tenant_id: int,
    entity_type: str,
    raw_data: Dict[str, Any]
) -> int:
    """Store raw extraction data and return the ID."""
    db = next(get_db_session())
    try:
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
        db.commit()

        return raw_data_id
    finally:
        db.close()


async def reset_job_countdown(tenant_id: int, job_id: int, message: str):
    """Update job status to FINISHED. Next run is calculated dynamically from last_updated_at + schedule_interval_minutes."""
    try:
        db = next(get_db_session())
        try:
            # Get the job details for logging
            job_query = text("""
                SELECT schedule_interval_minutes
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

            # Update job completion and calculate next run time
            from app.core.utils import DateTimeHelper
            from datetime import timedelta
            now = DateTimeHelper.now_default()

            # Get schedule interval to calculate next run time
            schedule_query = text("""
                SELECT schedule_interval_minutes
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            schedule_result = db.execute(schedule_query, {
                'job_id': job_id,
                'tenant_id': tenant_id
            }).fetchone()

            schedule_interval_minutes = schedule_result[0] if schedule_result else 360  # Default 6 hours
            next_run = now + timedelta(minutes=schedule_interval_minutes)

            update_query = text("""
                UPDATE etl_jobs
                SET status = 'READY',
                    last_run_finished_at = :now,
                    error_message = NULL,
                    retry_count = 0,
                    last_updated_at = :now,
                    next_run = :next_run
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'now': now,
                'next_run': next_run
            })
            db.commit()

            logger.info(f"✅ Jira job completed successfully - next run scheduled for {next_run}")

            logger.info(f"Job {job_id} completed successfully for tenant {tenant_id}: {message}")
            logger.info(f"Next run will be calculated as: last_updated_at + {schedule_interval_minutes} minutes")

            # Send WebSocket completion update
            from app.api.websocket_routes import get_websocket_manager
            websocket_manager = get_websocket_manager()
            await websocket_manager.send_completion_update(tenant_id, "Jira", True, {
                "message": message,
                "schedule_interval_minutes": schedule_interval_minutes
            })

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error updating job completion: {e}")


async def _extract_projects_and_issue_types(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    progress_tracker: JiraExtractionProgressTracker
) -> Dict[str, Any]:
    """Extract projects and issue types (Phase 2.1)."""

    # Step 1 progress: Extract projects data (0.0 -> 0.3)
    await progress_tracker.update_step_progress(
        1, 0.0, f"Fetching projects and issue types from {len(PROJECT_KEYS)} WEX projects"
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

    # Step 1 progress: Store raw data (0.3 -> 0.6)
    await progress_tracker.update_step_progress(
        1, 0.3, f"Storing {len(projects_list)} projects with issue types"
    )

    raw_data_id = await store_raw_extraction_data(
        integration_id, tenant_id, "jira_project_search", projects_data
    )

    # Step 1 progress: Process transformation (0.6 -> 1.0)
    await progress_tracker.update_step_progress(
        1, 0.6, f"Processing projects and issue types data (raw_data_id={raw_data_id})"
    )

    # Process transformation directly using project/search data structure
    from app.workers.transform_worker import TransformWorker
    transform_worker = TransformWorker()
    processed = transform_worker._process_jira_project_search(
        raw_data_id=raw_data_id,
        tenant_id=tenant_id,
        integration_id=integration_id
    )

    if not processed:
        raise ValueError("Failed to process projects transformation")

    # Count results (project/search uses 'issueTypes' camelCase, not 'issuetypes')
    issue_types_count = sum(len(project.get('issueTypes', [])) for project in projects_list)

    await progress_tracker.complete_step(
        1, f"Phase 2.1 complete: {len(projects_list)} projects, {issue_types_count} issue types"
    )

    return {
        "projects_count": len(projects_list),
        "issue_types_count": issue_types_count,
        "raw_data_id": raw_data_id
    }


async def _extract_statuses_and_relationships(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    progress_tracker: JiraExtractionProgressTracker
) -> Dict[str, Any]:
    """Extract statuses and project relationships (Phase 2.2) - following old ETL approach."""

    # Step 2 progress: Get projects from database (0.0 -> 0.2)
    await progress_tracker.update_step_progress(
        2, 0.0, "Fetching projects from database for status extraction"
    )

    # Get projects from database (like old ETL)
    db = next(get_db_session())
    try:
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

    finally:
        db.close()

    # Step 2 progress: Extract project-specific statuses (0.2 -> 0.8)
    await progress_tracker.update_step_progress(
        2, 0.2, f"Fetching project-specific statuses for {len(project_keys)} projects"
    )

    # Process each project's statuses individually (better granularity)
    total_statuses_processed = 0
    total_relationships_processed = 0

    for i, project_key in enumerate(project_keys):
        try:
            # Update progress for each project within step 2 (0.2 -> 0.8)
            project_progress = 0.2 + (i / len(project_keys)) * 0.6
            await progress_tracker.update_step_progress(
                2, project_progress, f"Processing project {i+1}/{len(project_keys)}: {project_key}"
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
                transform_worker = TransformWorker()
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
    await progress_tracker.complete_step(
        2, f"Phase 2.2 complete: {total_statuses_processed} statuses, {total_relationships_processed} project relationships across {len(project_keys)} projects"
    )

    return {
        "statuses_count": total_statuses_processed,
        "project_relationships_count": total_relationships_processed,
        "projects_processed": len(project_keys)
    }


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
    Manually trigger complete Jira extraction (projects, issue types, statuses, relationships).

    This endpoint:
    1. Validates the integration exists and is active
    2. Finds the corresponding ETL job
    3. Sets job status to RUNNING
    4. Triggers background extraction task for all phases
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

        # Add background task for complete extraction
        background_tasks.add_task(
            execute_projects_and_issue_types_extraction,
            integration_id,
            tenant_id,
            job_id
        )

        return {
            "success": True,
            "message": f"Complete Jira extraction started for {job_name}",
            "job_id": job_id,
            "integration_id": integration_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting complete Jira extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
