"""
Work Item Types (WITs) ETL Management API
Handles work item type mappings and hierarchies
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import Wit, WitMapping, WitHierarchy, Integration, User, QdrantVector

router = APIRouter()


class WitResponse(BaseModel):
    id: int
    external_id: Optional[str]
    original_name: str
    description: Optional[str]
    hierarchy_level: Optional[int]
    wits_mapping_id: Optional[int]
    integration_id: Optional[int]
    active: bool


class WitMappingResponse(BaseModel):
    id: int
    wit_from: str
    wit_to: str
    hierarchy_level: Optional[int]
    integration_id: Optional[int]
    integration_name: Optional[str]
    integration_logo: Optional[str]
    active: bool


class WitHierarchyResponse(BaseModel):
    id: int
    level_number: int
    level_name: str
    description: Optional[str]
    integration_id: Optional[int]
    integration_name: Optional[str]
    integration_logo: Optional[str]
    active: bool


class HierarchyDeletionRequest(BaseModel):
    target_hierarchy_id: Optional[int] = None


class HierarchyUpdateRequest(BaseModel):
    level_name: Optional[str] = None
    level_number: Optional[int] = None
    description: Optional[str] = None
    integration_id: Optional[int] = None
    active: Optional[bool] = None
    target_hierarchy_id: Optional[int] = None


class HierarchyCreateRequest(BaseModel):
    level_name: str
    level_number: int
    description: Optional[str] = None
    integration_id: Optional[int] = None


class WitMappingCreateRequest(BaseModel):
    wit_from: str
    wit_to: str
    hierarchy_level: int
    integration_id: Optional[int] = None


class WitMappingUpdateRequest(BaseModel):
    wit_from: Optional[str] = None
    wit_to: Optional[str] = None
    hierarchy_level: Optional[int] = None
    integration_id: Optional[int] = None
    active: Optional[bool] = None


@router.get("/wits", response_model=List[WitResponse])
async def get_wits(
    user: User = Depends(require_authentication)
):
    """Get all work item types for current user's tenant"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            wits = session.query(Wit).filter(
                Wit.tenant_id == user.tenant_id,
                Wit.active == True
            ).order_by(Wit.original_name).all()

            return [
                WitResponse(
                    id=wit.id,  # type: ignore
                    external_id=wit.external_id,  # type: ignore
                    original_name=wit.original_name,  # type: ignore
                    description=wit.description,  # type: ignore
                    hierarchy_level=wit.hierarchy_level,  # type: ignore
                    wits_mapping_id=wit.wit_mapping_id,  # type: ignore
                    integration_id=wit.integration_id,  # type: ignore
                    active=wit.active
                )
                for wit in wits
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch work item types: {str(e)}"
        )


@router.get("/wit-mappings", response_model=List[WitMappingResponse])
async def get_wit_mappings(
    user: User = Depends(require_authentication)
):
    """Get all work item type mappings for current user's tenant"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Query mappings with hierarchy and integration information, filtered by tenant
            # Use INNER JOIN to ensure we only get mappings with valid hierarchies
            mappings = session.query(WitMapping, WitHierarchy, Integration).join(
                WitHierarchy, WitMapping.wits_hierarchy_id == WitHierarchy.id
            ).outerjoin(
                Integration, WitMapping.integration_id == Integration.id
            ).filter(
                WitMapping.tenant_id == user.tenant_id,
                WitMapping.active == True,
                WitHierarchy.active == True  # Only include active hierarchies
            ).all()

            result = []
            for mapping, hierarchy, integration in mappings:
                result.append(WitMappingResponse(
                    id=mapping.id,
                    wit_from=mapping.wit_from,
                    wit_to=mapping.wit_to,
                    hierarchy_level=hierarchy.level_number,  # Always available due to INNER JOIN
                    integration_id=mapping.integration_id,
                    integration_name=integration.provider if integration else None,
                    integration_logo=integration.logo_filename if integration else None,
                    active=mapping.active
                ))

            return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch work item type mappings: {str(e)}"
        )


@router.get("/wits-hierarchies", response_model=List[WitHierarchyResponse])
async def get_wits_hierarchies(
    user: User = Depends(require_authentication)
):
    """Get all work item type hierarchies"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            hierarchies = session.query(
                WitHierarchy,
                Integration.provider.label('integration_name'),
                Integration.logo_filename.label('integration_logo')
            ).outerjoin(
                Integration, WitHierarchy.integration_id == Integration.id
            ).filter(
                WitHierarchy.tenant_id == user.tenant_id
            ).order_by(WitHierarchy.level_number.desc()).all()

            # If no real data, return 16 sample hierarchies as requested
            if not hierarchies:
                sample_hierarchies = [
                    WitHierarchyResponse(id=i, level_number=i-8, level_name=f"Level {i-8}", description=f"Hierarchy level {i-8} description", integration_id=1, integration_name="Jira", integration_logo="jira.svg", active=True)
                    for i in range(1, 17)
                ]
                return sample_hierarchies

            return [
                WitHierarchyResponse(
                    id=hierarchy.WitHierarchy.id,
                    level_number=hierarchy.WitHierarchy.level_number,
                    level_name=hierarchy.WitHierarchy.level_name,
                    description=hierarchy.WitHierarchy.description,
                    integration_id=hierarchy.WitHierarchy.integration_id,
                    integration_name=hierarchy.integration_name,
                    integration_logo=hierarchy.integration_logo,
                    active=hierarchy.WitHierarchy.active
                )
                for hierarchy in hierarchies
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch work item type hierarchies: {str(e)}"
        )


@router.put("/wits-hierarchies/{hierarchy_id}", response_model=WitHierarchyResponse)
async def update_wit_hierarchy(
    hierarchy_id: int,
    hierarchy_update: HierarchyUpdateRequest,
    user: User = Depends(require_authentication)
):
    """Update a WIT hierarchy with optional reassignment for deactivation"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Get the hierarchy
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(status_code=404, detail="Hierarchy not found")

            # Handle deactivation with potential reassignment
            if hierarchy_update.active is False and hierarchy.active is True:
                # Check for dependent mappings
                dependent_mappings = session.query(WitMapping).filter(
                    WitMapping.wits_hierarchy_id == hierarchy_id,
                    WitMapping.tenant_id == user.tenant_id
                ).all()

                # If there are dependencies and a target is specified, reassign them
                if dependent_mappings and hierarchy_update.target_hierarchy_id:
                    # Verify target hierarchy exists and is active
                    target_hierarchy = session.query(WitHierarchy).filter(
                        WitHierarchy.id == hierarchy_update.target_hierarchy_id,
                        WitHierarchy.active == True,
                        WitHierarchy.tenant_id == user.tenant_id
                    ).first()

                    if not target_hierarchy:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Target hierarchy (ID: {hierarchy_update.target_hierarchy_id}) not found or is inactive"
                        )

                    # Reassign all dependent mappings to the target hierarchy
                    for mapping in dependent_mappings:
                        mapping.wits_hierarchy_id = hierarchy_update.target_hierarchy_id  # type: ignore
                        # Update the wit_to field to match the target hierarchy's name
                        mapping.wit_to = target_hierarchy.level_name

            # Update fields if provided
            if hierarchy_update.level_name is not None:
                hierarchy.level_name = hierarchy_update.level_name  # type: ignore
            if hierarchy_update.level_number is not None:
                hierarchy.level_number = hierarchy_update.level_number  # type: ignore
            if hierarchy_update.description is not None:
                hierarchy.description = hierarchy_update.description  # type: ignore
            if hierarchy_update.integration_id is not None:
                hierarchy.integration_id = hierarchy_update.integration_id
            if hierarchy_update.active is not None:
                hierarchy.active = hierarchy_update.active

                # Update corresponding vectors in qdrant_vectors
                session.query(QdrantVector).filter(
                    QdrantVector.tenant_id == user.tenant_id,
                    QdrantVector.table_name == 'wits_hierarchies',
                    QdrantVector.record_id == hierarchy_id
                ).update({
                    'active': hierarchy_update.active,
                    'last_updated_at': DateTimeHelper.now_default()
                })

            # Update the last_updated_at timestamp using configured timezone
            hierarchy.last_updated_at = DateTimeHelper.now_default()
            session.commit()

            # Get integration info for response
            integration = session.query(Integration).filter(
                Integration.id == hierarchy.integration_id
            ).first() if hierarchy.integration_id else None

            # Return updated hierarchy data with integration info
            return WitHierarchyResponse(
                id=hierarchy.id,  # type: ignore
                level_number=hierarchy.level_number,  # type: ignore
                level_name=hierarchy.level_name,  # type: ignore
                description=hierarchy.description,  # type: ignore
                integration_id=hierarchy.integration_id,  # type: ignore
                integration_name=integration.provider if integration else None,  # type: ignore
                integration_logo=integration.logo_filename if integration else None,  # type: ignore
                active=hierarchy.active
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating hierarchy: {str(e)}")


@router.get("/wits-hierarchies/{hierarchy_id}/dependencies")
async def get_wit_hierarchy_dependencies(
    hierarchy_id: int,
    user: User = Depends(require_authentication)
):
    """Get dependencies for a WIT hierarchy before deletion/deactivation"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Get the hierarchy
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(status_code=404, detail="Hierarchy not found")

            # Get dependent mappings
            dependent_mappings = session.query(WitMapping).filter(
                WitMapping.wits_hierarchy_id == hierarchy_id,
                WitMapping.tenant_id == user.tenant_id
            ).all()

            # Get other active hierarchies for reassignment targets
            reassignment_targets = session.query(WitHierarchy).filter(
                WitHierarchy.id != hierarchy_id,
                WitHierarchy.active == True,
                WitHierarchy.tenant_id == user.tenant_id
            ).all()

            # Count affected work items
            total_affected_wits = 0
            mapping_details = []
            for mapping in dependent_mappings:
                wit_count = session.query(Wit).filter(
                    Wit.wits_mapping_id == mapping.id,
                    Wit.active == True
                ).count()
                total_affected_wits += wit_count

                mapping_details.append({
                    "id": mapping.id,
                    "wit_from": mapping.wit_from,
                    "wit_to": mapping.wit_to,
                    "affected_wits_count": wit_count
                })

            return {
                "hierarchy": {
                    "id": hierarchy.id,
                    "level_name": hierarchy.level_name,
                    "level_number": hierarchy.level_number
                },
                "has_dependencies": len(dependent_mappings) > 0,
                "dependency_count": len(dependent_mappings),
                "affected_wits_count": total_affected_wits,
                "dependent_mappings": mapping_details,
                "reassignment_targets": [
                    {
                        "id": target.id,
                        "level_name": target.level_name,
                        "level_number": target.level_number,
                        "description": target.description
                    }
                    for target in reassignment_targets
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking dependencies: {str(e)}")


@router.delete("/wits-hierarchies/{hierarchy_id}")
async def delete_wit_hierarchy(
    hierarchy_id: int,
    deletion_data: Optional[HierarchyDeletionRequest] = None,
    user: User = Depends(require_authentication)
):
    """Delete a WIT hierarchy with optional reassignment"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the hierarchy
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(status_code=404, detail="Hierarchy not found")

            # Get dependent mappings
            dependent_mappings = session.query(WitMapping).filter(
                WitMapping.wits_hierarchy_id == hierarchy_id,
                WitMapping.tenant_id == user.tenant_id
            ).all()

            # If there are dependencies and no deletion data provided, block deletion
            if dependent_mappings and not deletion_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete hierarchy. {len(dependent_mappings)} work item type mapping(s) are still using this hierarchy. Please specify reassignment options."
                )

            # Handle dependencies if deletion data is provided
            if deletion_data and dependent_mappings:
                if deletion_data.target_hierarchy_id:
                    # Verify target hierarchy exists and is active
                    target_hierarchy = session.query(WitHierarchy).filter(
                        WitHierarchy.id == deletion_data.target_hierarchy_id,
                        WitHierarchy.active == True,
                        WitHierarchy.tenant_id == user.tenant_id
                    ).first()

                    if not target_hierarchy:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Target hierarchy (ID: {deletion_data.target_hierarchy_id}) not found or is inactive"
                        )

                    # Reassign all dependent mappings to the target hierarchy
                    for mapping in dependent_mappings:
                        mapping.wits_hierarchy_id = deletion_data.target_hierarchy_id  # type: ignore
                        # Update the wit_to field to match the target hierarchy's name
                        mapping.wit_to = target_hierarchy.level_name

            session.delete(hierarchy)

            return {"message": "Hierarchy deleted successfully", "id": hierarchy_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting hierarchy: {str(e)}")


@router.post("/wits-hierarchies", response_model=WitHierarchyResponse)
async def create_wit_hierarchy(
    hierarchy_data: HierarchyCreateRequest,
    user: User = Depends(require_authentication)
):
    """Create a new work item type hierarchy"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Create new hierarchy
            new_hierarchy = WitHierarchy(
                level_name=hierarchy_data.level_name,
                level_number=hierarchy_data.level_number,
                description=hierarchy_data.description,
                integration_id=hierarchy_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=DateTimeHelper.now_default(),
                last_updated_at=DateTimeHelper.now_default()
            )

            session.add(new_hierarchy)
            session.flush()  # Get the ID

            # Get integration info if exists
            integration_name = None
            integration_logo = None
            if new_hierarchy.integration_id:
                integration = session.query(Integration).filter(
                    Integration.id == new_hierarchy.integration_id,
                    Integration.tenant_id == user.tenant_id
                ).first()
                if integration:
                    integration_name = integration.provider
                    integration_logo = integration.logo_filename

            return WitHierarchyResponse(
                id=new_hierarchy.id,  # type: ignore
                level_number=new_hierarchy.level_number,  # type: ignore
                level_name=new_hierarchy.level_name,  # type: ignore
                description=new_hierarchy.description,  # type: ignore
                integration_id=new_hierarchy.integration_id,  # type: ignore
                integration_name=integration_name,  # type: ignore
                integration_logo=integration_logo,  # type: ignore
                active=new_hierarchy.active
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create hierarchy: {str(e)}"
        )


@router.post("/wit-mappings", response_model=WitMappingResponse)
async def create_wit_mapping(
    mapping_data: WitMappingCreateRequest,
    user: User = Depends(require_authentication)
):
    """Create a new work item type mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Validate hierarchy level exists and is active
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.level_number == mapping_data.hierarchy_level,
                WitHierarchy.tenant_id == user.tenant_id,
                WitHierarchy.active == True
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active hierarchy level {mapping_data.hierarchy_level} not found"
                )

            # Create new mapping
            new_mapping = WitMapping(
                wit_from=mapping_data.wit_from,
                wit_to=mapping_data.wit_to,
                hierarchy_level=mapping_data.hierarchy_level,
                wits_hierarchy_id=hierarchy.id,
                integration_id=mapping_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=DateTimeHelper.now_default(),
                last_updated_at=DateTimeHelper.now_default()
            )

            session.add(new_mapping)
            session.flush()  # Get the ID

            # Get integration info if exists
            integration_name = None
            integration_logo = None
            if new_mapping.integration_id:
                integration = session.query(Integration).filter(
                    Integration.id == new_mapping.integration_id,
                    Integration.tenant_id == user.tenant_id
                ).first()
                if integration:
                    integration_name = integration.provider
                    integration_logo = integration.logo_filename

            return WitMappingResponse(
                id=new_mapping.id,  # type: ignore
                wit_from=new_mapping.wit_from,  # type: ignore
                wit_to=new_mapping.wit_to,  # type: ignore
                hierarchy_level=new_mapping.hierarchy_level,  # type: ignore
                integration_id=new_mapping.integration_id,  # type: ignore
                integration_name=integration_name,  # type: ignore
                integration_logo=integration_logo,  # type: ignore
                active=new_mapping.active
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create mapping: {str(e)}"
        )


@router.put("/wit-mappings/{mapping_id}", response_model=WitMappingResponse)
async def update_wit_mapping(
    mapping_id: int,
    mapping_data: WitMappingUpdateRequest,
    user: User = Depends(require_authentication)
):
    """Update a work item type mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Get the existing mapping
            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mapping not found"
                )

            # Update fields if provided
            if mapping_data.wit_from is not None:
                mapping.wit_from = mapping_data.wit_from  # type: ignore
            if mapping_data.wit_to is not None:
                mapping.wit_to = mapping_data.wit_to  # type: ignore
            if mapping_data.integration_id is not None:
                mapping.integration_id = mapping_data.integration_id
            if mapping_data.active is not None:
                mapping.active = mapping_data.active

                # Update corresponding vectors in qdrant_vectors
                session.query(QdrantVector).filter(
                    QdrantVector.tenant_id == user.tenant_id,
                    QdrantVector.table_name == 'wits_mappings',
                    QdrantVector.record_id == mapping_id
                ).update({
                    'active': mapping_data.active,
                    'last_updated_at': DateTimeHelper.now_default()
                })

            # Handle hierarchy level update
            if mapping_data.hierarchy_level is not None:
                # Validate hierarchy level exists and is active
                hierarchy = session.query(WitHierarchy).filter(
                    WitHierarchy.level_number == mapping_data.hierarchy_level,
                    WitHierarchy.tenant_id == user.tenant_id,
                    WitHierarchy.active == True
                ).first()

                if not hierarchy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Active hierarchy level {mapping_data.hierarchy_level} not found"
                    )

                mapping.wits_hierarchy_id = hierarchy.id

            mapping.last_updated_at = DateTimeHelper.now_default()
            session.commit()

            # Get updated hierarchy and integration info for response
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == mapping.wits_hierarchy_id
            ).first()

            integration = session.query(Integration).filter(
                Integration.id == mapping.integration_id
            ).first() if mapping.integration_id else None

            return WitMappingResponse(
                id=mapping.id,  # type: ignore
                wit_from=mapping.wit_from,  # type: ignore
                wit_to=mapping.wit_to,  # type: ignore
                hierarchy_level=hierarchy.level_number if hierarchy else None,  # type: ignore
                integration_id=mapping.integration_id,  # type: ignore
                integration_name=integration.provider if integration else None,  # type: ignore
                integration_logo=integration.logo_filename if integration else None,  # type: ignore
                active=mapping.active
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update mapping: {str(e)}"
        )


@router.delete("/wit-mappings/{mapping_id}")
async def delete_wit_mapping(
    mapping_id: int,
    user: User = Depends(require_authentication)
):
    """Delete a work item type mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the existing mapping
            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mapping not found"
                )

            # Check for dependent WITs
            from app.models.unified_models import Wit
            dependent_wits = session.query(Wit).filter(
                Wit.wits_mapping_id == mapping_id,
                Wit.active == True
            ).count()

            if dependent_wits > 0:
                # Soft delete to preserve referential integrity
                mapping.active = False
                from app.core.utils import DateTimeHelper
                mapping.last_updated_at = DateTimeHelper.now_default()
                session.commit()
                return {"message": f"Mapping deactivated successfully ({dependent_wits} dependent work items preserved)"}
            else:
                # Hard delete if no dependencies
                session.delete(mapping)
                session.commit()
                return {"message": "Mapping deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete mapping: {str(e)}"
        )
