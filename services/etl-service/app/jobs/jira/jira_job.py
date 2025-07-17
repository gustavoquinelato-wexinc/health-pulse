"""
Jira Passive Job

Implements the Jira sync portion of the Active/Passive Job Model.
This job:
1. Extracts all relevant issues from Jira
2. For each issue, calls the /dev_status endpoint
3. Stores raw dev_status JSON in JiraDevDetailsStaging table
4. On success: Sets GitHub job to PENDING and itself to FINISHED
5. On failure: Sets itself to PENDING with checkpoint data
"""

from sqlalchemy.orm import Session
from app.core.logging_config import get_logger
from app.core.config import AppConfig, get_settings
from app.core.utils import DateTimeHelper
from app.core.websocket_manager import get_websocket_manager
from app.models.unified_models import JobSchedule, JiraDevDetailsStaging, Integration, Issue
from typing import Dict, Any
import os

logger = get_logger(__name__)


async def run_jira_sync(session: Session, job_schedule: JobSchedule):
    """
    Main Jira sync function.
    
    Args:
        session: Database session
        job_schedule: JobSchedule record for this job
    """
    try:
        logger.info(f"Starting Jira sync job (ID: {job_schedule.id})")
        
        # Get Jira integration
        jira_integration = session.query(Integration).filter(
            Integration.name == "Jira"
        ).first()
        
        if not jira_integration:
            error_msg = "No Jira integration found. Please run initialize_integrations.py first."
            logger.error(f"ERROR: {error_msg}")
            job_schedule.set_pending_with_checkpoint(error_msg)
            session.commit()
            return
        
        # Setup Jira client
        from app.jobs.jira import JiraAPIClient
        
        key = AppConfig.load_key()
        jira_token = AppConfig.decrypt_token(jira_integration.password, key)
        jira_client = JiraAPIClient(
            username=jira_integration.username,
            token=jira_token,
            base_url=get_settings().JIRA_URL
        )
        
        # Extract issues and dev_status data
        result = await extract_jira_issues_and_dev_status(session, jira_integration, jira_client, job_schedule)
        
        if result['success']:
            # Success: Set GitHub job to PENDING and this job to FINISHED
            github_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'github_sync').first()
            if github_job:
                github_job.status = 'PENDING'
            
            job_schedule.set_finished()
            session.commit()
            
            logger.info(f"Jira sync completed successfully")
            logger.info(f"   • Issues processed: {result['issues_processed']}")
            logger.info(f"   • Dev status items staged: {result['dev_status_staged']}")
            logger.info(f"   • GitHub job set to PENDING")
            
        else:
            # Failure: Set this job back to PENDING with checkpoint
            error_msg = result.get('error', 'Unknown error')
            checkpoint = result.get('last_processed_updated_at')
            
            job_schedule.set_pending_with_checkpoint(error_msg, repo_checkpoint=checkpoint)
            session.commit()
            
            logger.error(f"Jira sync failed: {error_msg}")
            if checkpoint:
                logger.info(f"   • Checkpoint saved: {checkpoint}")
            
    except Exception as e:
        logger.error(f"Jira sync job error: {e}")
        import traceback
        traceback.print_exc()
        
        # Set job back to PENDING on unexpected error
        job_schedule.set_pending_with_checkpoint(str(e))
        session.commit()


async def extract_jira_issues_and_dev_status(session: Session, integration: Integration, jira_client, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Extract Jira issues and their dev_status data.

    Args:
        session: Database session
        integration: Jira integration object
        jira_client: Jira API client
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with extraction results
    """
    try:
        from app.jobs.jira.jira_extractors import extract_projects_and_issuetypes, extract_projects_and_statuses, extract_work_items_and_changelogs
        from app.core.logging_config import JobLogger

        job_logger = JobLogger("jira_sync")
        websocket_manager = get_websocket_manager()

        # Clear any previous progress and notify start
        websocket_manager.clear_job_progress("jira_sync")
        
        # Step 1: Extract projects and issue types
        logger.info("Step 1: Extracting projects and issue types...")
        await websocket_manager.send_progress_update("jira_sync", 10.0, "Extracting projects and issue types...")
        projects_result = extract_projects_and_issuetypes(session, jira_client, integration, job_logger)
        if not projects_result.get('projects_processed', 0):
            logger.warning("No projects found or processed")
            await websocket_manager.send_exception("jira_sync", "WARNING", "No projects found or processed")

        # Step 2: Extract projects and statuses
        logger.info("Step 2: Extracting projects and statuses...")
        await websocket_manager.send_progress_update("jira_sync", 20.0, "Extracting projects and statuses...")
        statuses_result = extract_projects_and_statuses(session, jira_client, integration, job_logger)
        if not statuses_result.get('statuses_processed', 0):
            logger.warning("No statuses found or processed")
            await websocket_manager.send_exception("jira_sync", "WARNING", "No statuses found or processed")

        # Step 3: Extract issues and changelogs
        logger.info("Step 3: Extracting issues and changelogs...")
        await websocket_manager.send_progress_update("jira_sync", 30.0, "Extracting issues and changelogs...")

        # Determine start date for incremental sync
        start_date = job_schedule.last_repo_sync_checkpoint or integration.last_sync_at
        if not start_date:
            # Default to 30 days ago for first run
            from datetime import timedelta
            start_date = DateTimeHelper.now_utc() - timedelta(days=30)

        # Start the extraction with periodic progress updates
        await websocket_manager.send_progress_update("jira_sync", 35.0, "Processing issues and changelogs...")

        issues_result = extract_work_items_and_changelogs(session, jira_client, integration, job_logger, start_date=start_date)

        if not issues_result['success']:
            return {
                'success': False,
                'error': f"Issues extraction failed: {issues_result.get('error', 'Unknown error')}",
                'issues_processed': 0,
                'dev_status_staged': 0
            }

        # Step 3.5: Issues and changelogs completed
        await websocket_manager.send_progress_update("jira_sync", 45.0, f"Processed {issues_result['issues_processed']} issues and {issues_result['changelogs_processed']} changelogs")

        # Step 4: Extract dev_status for issues with code_changed = True
        logger.info("Step 4: Extracting dev_status data...")
        await websocket_manager.send_progress_update("jira_sync", 50.0, "Extracting dev_status data...")

        # Get issues with code_changed = True
        issues_with_code_changes = session.query(Issue).filter(
            Issue.integration_id == integration.id,
            Issue.code_changed == True
        ).all()

        logger.info(f"Found {len(issues_with_code_changes)} issues with code changes")
        total_issues = len(issues_with_code_changes)

        # Clear existing staging records for this integration to avoid duplicates
        from app.models.unified_models import JiraDevDetailsStaging
        existing_count = session.query(JiraDevDetailsStaging).join(Issue).filter(
            Issue.integration_id == integration.id
        ).count()

        if existing_count > 0:
            logger.info(f"Clearing {existing_count} existing staging records for this integration...")
            session.query(JiraDevDetailsStaging).filter(
                JiraDevDetailsStaging.issue_id.in_(
                    session.query(Issue.id).filter(Issue.integration_id == integration.id)
                )
            ).delete(synchronize_session=False)
            session.commit()

        dev_status_staged = 0
        dev_status_skipped = 0
        issues_processed = 0

        for issue in issues_with_code_changes:
            try:
                if not issue.external_id:
                    logger.warning(f"Issue {issue.key} has no external_id, skipping")
                    continue

                # Fetch dev_status data from Jira
                dev_details = jira_client.get_issue_dev_details(issue.external_id)
                if dev_details:
                    # Import here to avoid circular imports
                    from app.jobs.jira.jira_extractors import has_useful_dev_status_data

                    # Filter: Only save staging records that contain actual PR or repository data
                    if has_useful_dev_status_data(dev_details):
                        # Store in staging table
                        staging_record = JiraDevDetailsStaging(
                            issue_id=issue.id,
                            dev_status_payload=dev_details,
                            processed=False,
                            client_id=integration.client_id
                        )
                        staging_record.set_dev_status_data(dev_details)
                        session.add(staging_record)
                        dev_status_staged += 1
                    else:
                        dev_status_skipped += 1
                        logger.debug(f"Skipped dev_status for issue {issue.key} (no useful data)")
                else:
                    dev_status_skipped += 1
                    logger.debug(f"No dev_status data for issue {issue.key}")

                issues_processed += 1

                # Update progress every 10 issues
                if issues_processed % 10 == 0:
                    progress = 50.0 + (issues_processed / total_issues) * 40.0  # 50% to 90%
                    await websocket_manager.send_progress_update(
                        "jira_sync",
                        progress,
                        f"Processing dev_status: {issues_processed}/{total_issues} issues"
                    )
                    logger.info(f"Processed dev_status for {issues_processed}/{total_issues} issues")
                    session.commit()  # Commit periodically

            except Exception as e:
                error_msg = f"Error processing dev_status for issue {issue.key}: {e}"
                logger.error(error_msg)
                await websocket_manager.send_exception("jira_sync", "ERROR", error_msg, str(e))
                continue

        # Final commit
        session.commit()

        # Step 5: All processing completed
        await websocket_manager.send_progress_update("jira_sync", 95.0, f"Completed: {issues_result['issues_processed']} issues, {issues_result['changelogs_processed']} changelogs, {dev_status_staged} dev_status records")

        # Send completion notification
        await websocket_manager.send_completion(
            "jira_sync",
            True,
            {
                'issues_processed': issues_result['issues_processed'],
                'changelogs_processed': issues_result['changelogs_processed'],
                'dev_status_staged': dev_status_staged
            }
        )

        logger.info(f"Jira extraction completed")
        logger.info(f"   • Issues processed: {issues_result['issues_processed']}")
        logger.info(f"   • Changelogs processed: {issues_result['changelogs_processed']}")
        logger.info(f"   • Dev status items staged: {dev_status_staged}")
        logger.info(f"   • Dev status items skipped (empty): {dev_status_skipped}")

        return {
            'success': True,
            'issues_processed': issues_result['issues_processed'],
            'changelogs_processed': issues_result['changelogs_processed'],
            'dev_status_staged': dev_status_staged
        }
        
    except Exception as e:
        logger.error(f"Error in Jira extraction: {e}")
        return {
            'success': False,
            'error': str(e),
            'issues_processed': 0,
            'dev_status_staged': 0
        }
