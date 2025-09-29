"""
Integrations ETL Management API
Handles integration management for ETL processes
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import Integration, User

router = APIRouter()


class IntegrationResponse(BaseModel):
    id: int
    name: str
    integration_type: str
    base_url: Optional[str]
    username: Optional[str]
    ai_model: Optional[str]
    logo_filename: Optional[str]
    active: bool
    last_sync_at: Optional[str]


@router.get("/integrations", response_model=List[IntegrationResponse])
async def get_integrations(
    user: User = Depends(require_authentication)
):
    """Get all integrations for current user's client"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Get integrations filtered by tenant_id and type='data' for ETL
            integrations = session.query(Integration).filter(
                Integration.tenant_id == user.tenant_id,
                Integration.type == 'data'
            ).order_by(Integration.provider).all()

            integration_responses = []
            for integration in integrations:
                # TODO: Get last sync time from etl_jobs table
                # For now, we'll set it to None
                last_sync_at = None

                integration_responses.append(IntegrationResponse(
                    id=integration.id,
                    name=integration.provider or "Unknown",
                    integration_type=integration.type or "Unknown",
                    base_url=integration.base_url,
                    username=integration.username,
                    ai_model=integration.ai_model,
                    logo_filename=integration.logo_filename,
                    active=integration.active,
                    last_sync_at=last_sync_at
                ))

            return integration_responses

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch integrations: {str(e)}"
        )
