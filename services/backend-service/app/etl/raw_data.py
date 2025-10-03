"""
Raw Data Storage APIs for ETL Service - Phase 1
Handles storage and retrieval of raw extraction data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db_session
from app.models.unified_models import Tenant
from app.etl.queue.queue_manager import get_queue_manager

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Pydantic Schemas (Inline)
# ============================================================================

class RawDataStoreRequest(BaseModel):
    """Request schema for storing raw extraction data."""
    integration_id: int = Field(..., description="Integration ID")
    entity_type: str = Field(..., description="Entity type (e.g., 'jira_issues_batch')")
    external_id: Optional[str] = Field(None, description="External batch ID")
    raw_data: Dict[str, Any] = Field(..., description="Complete API response")
    extraction_metadata: Optional[Dict[str, Any]] = Field(None, description="Extraction context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "integration_id": 1,
                "entity_type": "jira_issues_batch",
                "external_id": "batch_1",
                "raw_data": {
                    "issues": [{"key": "PROJ-1", "summary": "Issue 1"}],
                    "total": 1000
                },
                "extraction_metadata": {
                    "jql": "project = PROJ",
                    "batch_number": 1,
                    "cursor": "abc123"
                }
            }
        }


class RawDataStoreResponse(BaseModel):
    """Response schema for store operation."""
    success: bool
    raw_data_id: int
    message: str
    queued: bool = False


class RawDataStatusUpdateRequest(BaseModel):
    """Request schema for updating processing status."""
    processing_status: str = Field(..., description="New status (pending/processing/completed/failed)")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if failed")


class RawDataStatusUpdateResponse(BaseModel):
    """Response schema for status update."""
    success: bool
    message: str


class RawDataInfo(BaseModel):
    """Schema for raw data record information."""
    id: int
    tenant_id: int
    integration_id: int
    entity_type: str
    external_id: Optional[str]
    processing_status: str
    created_at: datetime
    processed_at: Optional[datetime]
    raw_data_size: int  # Number of items in raw_data
    has_errors: bool


class RawDataListResponse(BaseModel):
    """Response schema for list operation."""
    raw_data_records: List[RawDataInfo]
    total_count: int
    limit: int
    offset: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/raw-data/store", response_model=RawDataStoreResponse)
async def store_raw_data(
    request: RawDataStoreRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    queue_transform: bool = Query(True, description="Queue for transformation"),
    db: Session = Depends(get_db_session)
):
    """
    Store raw extraction data and optionally queue for transformation.
    
    This endpoint:
    1. Stores complete API response in raw_extraction_data table
    2. Optionally publishes transform job to RabbitMQ queue
    
    Batch Processing:
    - 1 API call = 1 database record = 1 queue message
    - raw_data contains ALL items in the batch (e.g., 1000 Jira issues)
    - Queue message contains only the raw_data_id (small, efficient)
    """
    try:
        # Verify tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
        
        # Insert raw data record
        from sqlalchemy import text
        insert_query = text("""
            INSERT INTO raw_extraction_data (
                tenant_id, integration_id, entity_type, external_id,
                raw_data, extraction_metadata, processing_status,
                created_at, active
            ) VALUES (
                :tenant_id, :integration_id, :entity_type, :external_id,
                :raw_data::jsonb, :extraction_metadata::jsonb, 'pending',
                NOW(), TRUE
            ) RETURNING id
        """)
        
        import json
        result = db.execute(insert_query, {
            'tenant_id': tenant_id,
            'integration_id': request.integration_id,
            'entity_type': request.entity_type,
            'external_id': request.external_id,
            'raw_data': json.dumps(request.raw_data),
            'extraction_metadata': json.dumps(request.extraction_metadata) if request.extraction_metadata else None
        })
        
        raw_data_id = result.fetchone()[0]  # type: ignore
        db.commit()
        
        logger.info(f"Raw data stored: ID={raw_data_id}, tenant={tenant_id}, type={request.entity_type}")
        
        # Queue for transformation if requested
        queued = False
        if queue_transform:
            try:
                queue_manager = get_queue_manager()
                queued = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=request.integration_id,
                    raw_data_id=raw_data_id,
                    data_type=request.entity_type
                )
                if queued:
                    logger.info(f"Transform job queued for raw_data_id={raw_data_id}")
            except Exception as e:
                logger.error(f"Failed to queue transform job: {e}")
                # Don't fail the request if queuing fails
        
        return RawDataStoreResponse(
            success=True,
            raw_data_id=raw_data_id,
            message=f"Raw data stored successfully (ID: {raw_data_id})",
            queued=queued
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing raw data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store raw data: {str(e)}")


@router.get("/raw-data", response_model=RawDataListResponse)
async def get_raw_data_list(
    tenant_id: int = Query(..., description="Tenant ID"),
    integration_id: Optional[int] = Query(None, description="Filter by integration ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    processing_status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db_session)
):
    """
    Retrieve list of raw extraction data records.
    
    Supports filtering by:
    - integration_id
    - entity_type
    - processing_status
    """
    try:
        # Build query
        from sqlalchemy import text
        
        # Base query
        where_clauses = ["tenant_id = :tenant_id", "active = TRUE"]
        params = {'tenant_id': tenant_id, 'limit': limit, 'offset': offset}
        
        if integration_id:
            where_clauses.append("integration_id = :integration_id")
            params['integration_id'] = integration_id
        
        if entity_type:
            where_clauses.append("entity_type = :entity_type")
            params['entity_type'] = entity_type  # type: ignore
        
        if processing_status:
            where_clauses.append("processing_status = :processing_status")
            params['processing_status'] = processing_status  # type: ignore
        
        where_clause = " AND ".join(where_clauses)
        
        # Get total count
        count_query = text(f"""
            SELECT COUNT(*) FROM raw_extraction_data
            WHERE {where_clause}
        """)
        total_count = db.execute(count_query, params).scalar()
        
        # Get records
        select_query = text(f"""
            SELECT 
                id, tenant_id, integration_id, entity_type, external_id,
                processing_status, created_at, processed_at,
                jsonb_array_length(COALESCE(raw_data->'issues', raw_data->'pull_requests', '[]'::jsonb)) as raw_data_size,
                CASE WHEN error_details IS NOT NULL THEN TRUE ELSE FALSE END as has_errors
            FROM raw_extraction_data
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        results = db.execute(select_query, params).fetchall()
        
        # Convert to response format
        records = [
            RawDataInfo(
                id=row[0],
                tenant_id=row[1],
                integration_id=row[2],
                entity_type=row[3],
                external_id=row[4],
                processing_status=row[5],
                created_at=row[6],
                processed_at=row[7],
                raw_data_size=row[8] or 0,
                has_errors=row[9]
            )
            for row in results
        ]
        
        return RawDataListResponse(
            raw_data_records=records,
            total_count=total_count or 0,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error retrieving raw data list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve raw data: {str(e)}")


@router.put("/raw-data/{raw_data_id}/status", response_model=RawDataStatusUpdateResponse)
async def update_raw_data_status(
    raw_data_id: int,
    request: RawDataStatusUpdateRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Update processing status of a raw data record.
    
    Valid statuses:
    - pending: Waiting for processing
    - processing: Currently being processed
    - completed: Successfully processed
    - failed: Processing failed
    """
    try:
        # Validate status
        valid_statuses = ['pending', 'processing', 'completed', 'failed']
        if request.processing_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update status
        from sqlalchemy import text
        import json
        
        update_query = text("""
            UPDATE raw_extraction_data
            SET 
                processing_status = :status,
                error_details = :error_details::jsonb,
                processed_at = CASE WHEN :status IN ('completed', 'failed') THEN NOW() ELSE processed_at END
            WHERE id = :raw_data_id AND tenant_id = :tenant_id
            RETURNING id
        """)
        
        result = db.execute(update_query, {
            'raw_data_id': raw_data_id,
            'tenant_id': tenant_id,
            'status': request.processing_status,
            'error_details': json.dumps(request.error_details) if request.error_details else None
        })
        
        if hasattr(result, 'rowcount') and getattr(result, 'rowcount', 1) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Raw data record {raw_data_id} not found for tenant {tenant_id}"
            )
        
        db.commit()
        
        logger.info(f"Raw data status updated: ID={raw_data_id}, status={request.processing_status}")
        
        return RawDataStatusUpdateResponse(
            success=True,
            message=f"Status updated to '{request.processing_status}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating raw data status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

