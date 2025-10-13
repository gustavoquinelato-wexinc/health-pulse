"""
ETL Custom Fields API
Handles custom field mapping and discovery for Jira integrations
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
import json
import os

from app.core.database import get_db_session
from app.auth.auth_middleware import require_authentication, UserData
from app.models.unified_models import Integration

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class CustomFieldMappingResponse:
    """Response model for custom field mappings"""
    def __init__(self, custom_field_mappings: Dict[str, Any], available_columns: List[str], mapped_columns: List[str]):
        self.custom_field_mappings = custom_field_mappings
        self.available_columns = available_columns
        self.mapped_columns = mapped_columns


# ============================================================================
# Helper Functions
# ============================================================================

def get_available_custom_field_columns() -> List[str]:
    """Get list of available custom field columns (custom_field_01 through custom_field_20)"""
    return [f"custom_field_{i:02d}" for i in range(1, 21)]


def get_mapped_columns_from_config(custom_field_mappings: Dict[str, Any]) -> List[str]:
    """Extract mapped columns from custom field mappings configuration"""
    mapped_columns = []
    for field_id, config in custom_field_mappings.items():
        if isinstance(config, dict) and config.get('mapped_column'):
            mapped_columns.append(config['mapped_column'])
    return mapped_columns


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/custom-fields/mappings/{integration_id}")
async def get_custom_field_mappings(
    integration_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get custom field mappings for a specific integration.
    Returns the current mappings configuration and available columns.
    """
    try:
        # Get integration and verify access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # Get custom field mappings from integration configuration
        custom_field_mappings = integration.custom_field_mappings or {}

        # Ensure custom_field_mappings is a dict
        if not isinstance(custom_field_mappings, dict):
            custom_field_mappings = {}

        # Get available and mapped columns
        available_columns = get_available_custom_field_columns()
        mapped_columns = get_mapped_columns_from_config(custom_field_mappings)
        
        return {
            "success": True,
            "custom_field_mappings": custom_field_mappings,
            "available_columns": available_columns,
            "mapped_columns": mapped_columns,
            "integration_id": integration_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting custom field mappings for integration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get custom field mappings")


@router.put("/custom-fields/mappings/{integration_id}")
async def update_custom_field_mappings(
    integration_id: int,
    request_data: Dict[str, Any],
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Update custom field mappings for a specific integration.
    Saves the mappings configuration to the integration record.
    """
    try:
        # Get integration and verify access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # Extract custom field mappings from request
        custom_field_mappings = request_data.get('custom_field_mappings', {})
        
        # Validate mappings format
        available_columns = get_available_custom_field_columns()
        for field_id, config in custom_field_mappings.items():
            if isinstance(config, dict):
                mapped_column = config.get('mapped_column')
                if mapped_column and mapped_column != 'overflow' and mapped_column not in available_columns:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid mapped column: {mapped_column}. Must be one of {available_columns} or 'overflow'"
                    )
        
        # Update integration with new mappings
        integration.custom_field_mappings = custom_field_mappings
        db.commit()
        
        logger.info(f"Updated custom field mappings for integration {integration_id}")
        
        return {
            "success": True,
            "message": "Custom field mappings updated successfully",
            "integration_id": integration_id,
            "mappings_count": len(custom_field_mappings)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating custom field mappings for integration {integration_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update custom field mappings")


@router.get("/custom-fields/list/{integration_id}")
async def list_custom_fields(
    integration_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get list of custom fields from custom_fields table for a specific integration.
    Returns all discovered custom fields filtered by integration_id and tenant_id.
    """
    try:
        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Query custom_fields table
        from app.models.unified_models import CustomField

        custom_fields = db.query(CustomField).filter(
            CustomField.integration_id == integration_id,
            CustomField.tenant_id == user.tenant_id,
            CustomField.active == True
        ).order_by(CustomField.name).all()

        # Convert to response format
        fields_list = [
            {
                "id": field.id,
                "external_id": field.external_id,
                "name": field.name,
                "field_type": field.field_type,
                "operations": field.operations
            }
            for field in custom_fields
        ]

        return {
            "success": True,
            "custom_fields": fields_list,
            "total_count": len(fields_list),
            "integration_id": integration_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching custom fields for integration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch custom fields")


@router.get("/custom-fields/mappings-table/{integration_id}")
async def get_custom_field_mappings_table(
    integration_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get custom field mappings from custom_fields_mapping table.
    Returns the mapping of custom_field_XX_id to custom_fields.id.
    """
    try:
        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Query custom_fields_mapping table
        from app.models.unified_models import CustomFieldMapping

        mapping_record = db.query(CustomFieldMapping).filter(
            CustomFieldMapping.integration_id == integration_id,
            CustomFieldMapping.tenant_id == user.tenant_id,
            CustomFieldMapping.active == True
        ).first()

        # Build response with all 20 mappings
        mappings = {}
        if mapping_record:
            for i in range(1, 21):
                field_key = f"custom_field_{i:02d}"
                field_id_attr = f"custom_field_{i:02d}_id"
                field_id = getattr(mapping_record, field_id_attr, None)
                mappings[field_key] = field_id
        else:
            # No mapping record exists yet, return empty mappings
            for i in range(1, 21):
                field_key = f"custom_field_{i:02d}"
                mappings[field_key] = None

        return {
            "success": True,
            "mappings": mappings,
            "integration_id": integration_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching custom field mappings table for integration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch custom field mappings")


@router.put("/custom-fields/mappings-table/{integration_id}")
async def update_custom_field_mappings_table(
    integration_id: int,
    request_data: Dict[str, Any],
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Update custom field mappings in custom_fields_mapping table.
    Expects mappings in format: { "custom_field_01": 123, "custom_field_02": 456, ... }
    """
    try:
        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Get mappings from request
        mappings = request_data.get('mappings', {})

        # Query or create custom_fields_mapping record
        from app.models.unified_models import CustomFieldMapping

        mapping_record = db.query(CustomFieldMapping).filter(
            CustomFieldMapping.integration_id == integration_id,
            CustomFieldMapping.tenant_id == user.tenant_id
        ).first()

        if not mapping_record:
            # Create new mapping record
            mapping_record = CustomFieldMapping(
                integration_id=integration_id,
                tenant_id=user.tenant_id,
                active=True
            )
            db.add(mapping_record)

        # Update all 20 mapping fields
        for i in range(1, 21):
            field_key = f"custom_field_{i:02d}"
            field_id_attr = f"custom_field_{i:02d}_id"
            field_id = mappings.get(field_key)
            setattr(mapping_record, field_id_attr, field_id)

        db.commit()

        logger.info(f"Updated custom field mappings table for integration {integration_id}")

        return {
            "success": True,
            "message": "Custom field mappings updated successfully",
            "integration_id": integration_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating custom field mappings table for integration {integration_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update custom field mappings")


@router.get("/custom-fields/version-check")
async def version_check():
    """Simple endpoint to verify the updated code is loaded"""
    return {"version": "fixed_single_record_v2", "message": "Updated code loaded successfully"}

@router.post("/custom-fields/sync/{integration_id}")
async def sync_custom_fields(
    integration_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Trigger custom field sync for an integration using Jira createmeta API.
    Similar to ETL jobs, this will request Jira data, extract custom fields, and queue for processing.
    """
    logger.info(f"Starting custom fields sync for integration {integration_id}, user: {user.user_id}, tenant: {user.tenant_id}")

    try:
        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Only support Jira integrations
        if integration.provider.lower() != 'jira':
            raise HTTPException(status_code=400, detail="Custom field sync only supported for Jira integrations")

        # Get project keys from integration settings
        settings = integration.settings or {}
        project_keys = settings.get('projects', [])

        if not project_keys:
            raise HTTPException(status_code=400, detail="No projects configured in integration settings")
        logger.info(f"Starting custom fields sync for integration {integration_id} with projects: {project_keys}")

        # Perform custom fields discovery using Jira createmeta API
        from app.etl.jira_client import JiraAPIClient, extract_custom_fields_from_createmeta
        from datetime import datetime, timezone

        try:
            # Create Jira client from integration
            jira_client = JiraAPIClient.create_from_integration(integration)

            # Call createmeta API for all projects (single call for efficiency)
            logger.info(f"Calling Jira createmeta API for projects: {project_keys}")
            createmeta_response = jira_client.get_createmeta(
                project_keys=project_keys,
                issue_type_names=None,  # 🔧 FIX: Get ALL issue types, not just "Story"
                expand="projects.issuetypes.fields"
            )

            # 🔍 DEBUG: Log the size of the response for troubleshooting
            response_json = json.dumps(createmeta_response)
            response_size_bytes = len(response_json.encode('utf-8'))
            response_size_mb = response_size_bytes / 1024 / 1024
            projects_count = len(createmeta_response.get('projects', []))
            logger.info(f"🔍 DEBUG: Createmeta response size: {response_size_bytes:,} bytes ({response_size_mb:.2f} MB), projects: {projects_count}")

            # Store one record with all projects and queue single message
            projects_processed = 0
            total_custom_fields = 0

            if user.tenant_id is not None:
                projects = createmeta_response.get('projects', [])
                projects_processed = len(projects)

                # Extract custom fields from the full response (all projects)
                all_discovered_fields = extract_custom_fields_from_createmeta(createmeta_response)
                total_custom_fields = len(all_discovered_fields)

                # Queue createmeta response (first message)
                await queue_custom_fields_for_processing(
                    integration_id=integration_id,
                    tenant_id=user.tenant_id,
                    project_key=None,  # No specific project - this is for all projects
                    project_name=None,
                    discovered_fields=all_discovered_fields,
                    createmeta_response=createmeta_response  # FULL original response with all projects
                )

                logger.info(f"Stored createmeta raw data and queued for processing: projects_count={projects_processed}, fields_count={total_custom_fields}")

                # Fetch special fields separately (not available in createmeta)
                # This creates a SECOND queue message and raw_extraction_data entry with different type
                development_field_id = os.getenv('JIRA_DEVELOPMENT_FIELD_ID', 'customfield_10000')
                logger.info(f"Fetching special field (development): {development_field_id}")

                development_field_response = jira_client.get_field_by_id(development_field_id)
                if development_field_response:
                    logger.info(f"Successfully fetched special field: {development_field_response.get('id')} - {development_field_response.get('name')}")

                    # Queue special field as SECOND message with type 'jira_special_fields'
                    await queue_special_fields_for_processing(
                        integration_id=integration_id,
                        tenant_id=user.tenant_id,
                        field_search_response=development_field_response  # Field search API response
                    )

                    total_custom_fields += 1
                    logger.info(f"Stored special field raw data and queued for processing")
                else:
                    logger.warning(f"Special field {development_field_id} not found")

                logger.info(f"Total custom fields sync completed: {total_custom_fields} fields (including development field)")
            else:
                logger.warning("User tenant_id is None, skipping queue processing")

            etl_result = {
                "status": "completed",
                "projects_processed": projects_processed,
                "total_custom_fields": total_custom_fields,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to sync custom fields: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve custom fields: {str(e)}")

        return {
            "success": True,
            "message": f"Custom fields sync completed successfully for {etl_result.get('projects_processed', 0)} projects.",
            "integration_id": integration_id,
            "project_keys": project_keys,
            "sync_status": etl_result.get("status", "completed"),
            "projects_processed": etl_result.get("projects_processed", 0),
            "total_custom_fields": etl_result.get("total_custom_fields", 0),
            "timestamp": etl_result.get("timestamp")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing custom fields for integration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync custom fields")


@router.post("/custom-fields/discover")
async def discover_custom_fields(
    request_data: Dict[str, Any],
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Trigger custom field discovery for a project.
    This is a placeholder for future implementation that would call Jira API.
    """
    try:
        project_id = request_data.get('project_id')
        integration_id = request_data.get('integration_id')
        force_refresh = request_data.get('force_refresh', False)

        if not project_id or not integration_id:
            raise HTTPException(status_code=400, detail="project_id and integration_id are required")

        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # TODO: Implement actual Jira API discovery
        # For now, return mock data
        discovered_fields = [
            {
                "jira_field_id": "customfield_10001",
                "jira_field_name": "Story Points",
                "jira_field_type": "number",
                "project_count": 1
            },
            {
                "jira_field_id": "customfield_10002",
                "jira_field_name": "Epic Link",
                "jira_field_type": "string",
                "project_count": 1
            }
        ]

        discovered_issue_types = [
            {
                "issue_type_id": "10001",
                "issue_type_name": "Story",
                "project_count": 1
            },
            {
                "issue_type_id": "10002",
                "issue_type_name": "Epic",
                "project_count": 1
            }
        ]

        return {
            "success": True,
            "project_id": project_id,
            "integration_id": integration_id,
            "discovered_fields": discovered_fields,
            "discovered_issue_types": discovered_issue_types,
            "discovery_timestamp": "2025-10-02T19:30:00Z"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering custom fields: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover custom fields")


@router.get("/custom-fields/discovered/{project_id}/{integration_id}")
async def get_discovered_custom_fields(
    project_id: int,
    integration_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get previously discovered custom fields for a project.
    This is a placeholder for future implementation.
    """
    try:
        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # TODO: Implement actual database lookup
        # For now, return empty data
        return {
            "success": True,
            "data": []
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting discovered custom fields: {e}")
        raise HTTPException(status_code=500, detail="Failed to get discovered custom fields")


async def queue_custom_fields_for_processing(
    integration_id: int,
    tenant_id: int,
    discovered_fields: List[Dict[str, Any]],
    createmeta_response: Dict[str, Any],
    project_key: Optional[str] = None,
    project_name: Optional[str] = None
):
    """
    Store large payload in raw_extraction_data table and queue only reference ID.
    This approach handles large payloads efficiently and provides audit trail.
    """
    try:
        from app.etl.queue.queue_manager import QueueManager
        from datetime import datetime, timezone
        from sqlalchemy import text
        import json
        from app.core.database import get_database



        # Step 1: Store full payload in raw_extraction_data table
        # Use database session context manager
        database = get_database()

        with database.get_session_context() as db:
            try:
                # Store the raw API response (either createmeta or field search)
                # Each API call gets its own raw_extraction_data entry

                # Insert into raw_extraction_data (simplified structure)
                insert_query = text("""
                    INSERT INTO raw_extraction_data (
                        type, raw_data, status, tenant_id, integration_id, created_at, last_updated_at, active
                    ) VALUES (
                        :type, CAST(:raw_data AS jsonb), 'pending', :tenant_id, :integration_id, NOW(), NOW(), TRUE
                    ) RETURNING id
                """)

                # 🔍 DEBUG: Log the size being stored in database
                raw_data_json = json.dumps(createmeta_response)
                db_size_bytes = len(raw_data_json.encode('utf-8'))
                db_size_mb = db_size_bytes / 1024 / 1024
                logger.info(f"🔍 DEBUG: Storing in database: {db_size_bytes:,} bytes ({db_size_mb:.2f} MB)")

                result = db.execute(insert_query, {
                    'type': 'jira_custom_fields',
                    'raw_data': raw_data_json,  # EXACT API response, no wrapping
                    'tenant_id': tenant_id,
                    'integration_id': integration_id
                })

                row = result.fetchone()
                if row is None:
                    raise Exception("Failed to insert raw data - no ID returned")
                raw_data_id = row[0]
                db.commit()

                logger.info(f"🔍 DEBUG: Successfully stored raw_data with ID: {raw_data_id}")

                logger.info(f"Stored raw data: ID={raw_data_id}, project={project_key}")

            except Exception as db_error:
                db.rollback()
                logger.error(f"Database error storing raw data for project {project_key}: {db_error}")
                raise

        logger.info(f"Stored custom fields data in raw_extraction_data: ID={raw_data_id}, project={project_key}")

        # Step 2: Queue lightweight reference message to tenant-specific transform queue
        queue_manager = QueueManager()

        # Publish lightweight message to tenant-specific transform queue
        success = queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=raw_data_id,
            data_type='jira_custom_fields'
        )

        if success:
            logger.info(f"✅ Queued custom fields for processing: raw_data_id={raw_data_id}, project={project_key}, tenant={tenant_id}")
        else:
            logger.error(f"❌ Failed to queue custom fields for processing: raw_data_id={raw_data_id}, project={project_key}, tenant={tenant_id}")
            raise Exception("Failed to queue custom fields for processing")

    except Exception as e:
        logger.error(f"Failed to store/queue custom fields data: {e}")
        # Don't raise exception here - the discovery was successful even if storage/queuing failed


async def queue_special_fields_for_processing(
    integration_id: int,
    tenant_id: int,
    field_search_response: Dict[str, Any]
):
    """
    Store special field response in raw_extraction_data and queue for processing.
    Uses type 'jira_special_fields' to differentiate from createmeta.

    Special fields are those not available in createmeta API (e.g., development field).
    This function can handle any field fetched via /rest/api/3/field/search API.

    Args:
        integration_id: Integration ID
        tenant_id: Tenant ID
        field_search_response: Response from /rest/api/3/field/search API
    """
    try:
        from app.etl.queue.queue_manager import QueueManager
        from sqlalchemy import text
        import json
        from app.core.database import get_database

        database = get_database()

        with database.get_session_context() as db:
            try:
                # Insert into raw_extraction_data with type 'jira_special_fields'
                insert_query = text("""
                    INSERT INTO raw_extraction_data (
                        type, raw_data, status, tenant_id, integration_id, created_at, last_updated_at, active
                    ) VALUES (
                        :type, CAST(:raw_data AS jsonb), 'pending', :tenant_id, :integration_id, NOW(), NOW(), TRUE
                    ) RETURNING id
                """)

                raw_data_json = json.dumps(field_search_response)
                logger.info(f"🔍 DEBUG: Storing special field in database")

                result = db.execute(insert_query, {
                    'type': 'jira_special_fields',  # Generic type for special fields
                    'raw_data': raw_data_json,
                    'tenant_id': tenant_id,
                    'integration_id': integration_id
                })

                row = result.fetchone()
                if row is None:
                    raise Exception("Failed to insert special field raw data - no ID returned")
                raw_data_id = row[0]
                db.commit()

                logger.info(f"🔍 DEBUG: Successfully stored special field raw_data with ID: {raw_data_id}")

            except Exception as db_error:
                db.rollback()
                logger.error(f"Database error storing special field raw data: {db_error}")
                raise

        # Queue message to tenant-specific transform queue
        queue_manager = QueueManager()

        success = queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            raw_data_id=raw_data_id,
            data_type='jira_special_fields'  # Generic data type for worker routing
        )

        if success:
            logger.info(f"✅ Queued special field for processing: raw_data_id={raw_data_id}, tenant={tenant_id}")
        else:
            logger.error(f"❌ Failed to queue special field for processing: raw_data_id={raw_data_id}, tenant={tenant_id}")
            raise Exception("Failed to queue special field for processing")

    except Exception as e:
        logger.error(f"Failed to store/queue special field data: {e}")
        # Don't raise exception here - the discovery was successful even if storage/queuing failed


@router.get("/issue-types/discovered/{project_id}/{integration_id}")
async def get_discovered_issue_types(
    project_id: int,
    integration_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get previously discovered issue types for a project.
    This is a placeholder for future implementation.
    """
    try:
        # Verify integration access
        integration = db.query(Integration).filter(
            Integration.id == integration_id,
            Integration.tenant_id == user.tenant_id,
            Integration.active == True
        ).first()
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # TODO: Implement actual database lookup
        # For now, return empty data
        return {
            "success": True,
            "data": []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting discovered issue types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get discovered issue types")
