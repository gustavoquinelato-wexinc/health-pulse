# Mapping Tables Vectorization Support Fix

**Date**: 2025-10-11  
**Issue**: VectorizationWorker error "Unknown table name: wits_hierarchies" when queueing mapping tables for vectorization

## Problem

When testing the hierarchies mapping queue for vectorization in the ETL frontend, the VectorizationWorker threw an error:

```
ERROR - Unknown table name: wits_hierarchies
```

The issue occurred because the VectorizationWorker was missing support for the four Jira mapping tables:
1. `wits_hierarchies` - Work Item Type hierarchy levels
2. `wits_mappings` - Work Item Type mappings to standardized types
3. `statuses_mappings` - Status mappings to workflow steps
4. `workflows` - Workflow step definitions

## Root Cause

The VectorizationWorker had three missing pieces for mapping tables:

1. **Missing Model Imports**: The mapping table models (`WitHierarchy`, `WitMapping`, `StatusMapping`, `Workflow`) were not imported
2. **Missing TABLE_MODEL_MAP Entries**: The four mapping tables were not included in the `TABLE_MODEL_MAP` dictionary
3. **Missing _fetch_entity Logic**: No special handling for mapping tables which use internal IDs instead of external IDs
4. **Missing _prepare_entity_data Methods**: No data preparation methods for the four mapping tables
5. **Table Name Inconsistency**: API endpoint accepted `status_mappings` but database table is `statuses_mappings`

## Solution

### 1. Updated Model Imports

**File**: `services/backend-service/app/workers/vectorization_worker.py`

Added mapping table models to imports:

```python
from app.models.unified_models import (
    WorkItem, Changelog, Project, Status, Wit,
    Pr, PrCommit, PrReview, PrComment, Repository,
    WorkItemPrLink, Integration, QdrantVector,
    WitHierarchy, WitMapping, StatusMapping, Workflow  # Added
)
```

### 2. Updated TABLE_MODEL_MAP

Added mapping tables to the model mapping dictionary:

```python
TABLE_MODEL_MAP = {
    'work_items': WorkItem,
    'changelogs': Changelog,
    'projects': Project,
    'statuses': Status,
    'wits': Wit,
    'prs': Pr,
    'prs_commits': PrCommit,
    'prs_reviews': PrReview,
    'prs_comments': PrComment,
    'repositories': Repository,
    'work_items_prs_links': WorkItemPrLink,
    # Mapping tables (use internal ID)
    'wits_hierarchies': WitHierarchy,
    'wits_mappings': WitMapping,
    'statuses_mappings': StatusMapping,
    'workflows': Workflow
}
```

### 3. Updated _fetch_entity Method

Added special case handling for mapping tables which use internal IDs:

```python
# Special case for mapping tables: use internal ID
elif table_name in ['wits_hierarchies', 'wits_mappings', 'statuses_mappings', 'workflows']:
    entity = session.query(model).filter(
        model.id == int(external_id),
        model.tenant_id == tenant_id,
        model.active == True
    ).first()
```

### 4. Added _prepare_entity_data Methods

Added data preparation methods for all four mapping tables:

#### wits_hierarchies
```python
elif table_name == "wits_hierarchies":
    integration_name = ""
    if entity.integration:
        integration_name = entity.integration.provider or ""
    
    return {
        "level_name": entity.level_name or "",
        "level_number": entity.level_number or 0,
        "description": entity.description or "",
        "integration_name": integration_name
    }
```

#### wits_mappings
```python
elif table_name == "wits_mappings":
    hierarchy_level = None
    hierarchy_name = ""
    if entity.wit_hierarchy:
        hierarchy_level = entity.wit_hierarchy.level_number
        hierarchy_name = entity.wit_hierarchy.level_name or ""
    
    integration_name = ""
    if entity.integration:
        integration_name = entity.integration.provider or ""
    
    return {
        "wit_from": entity.wit_from or "",
        "wit_to": entity.wit_to or "",
        "hierarchy_level": hierarchy_level or 0,
        "hierarchy_name": hierarchy_name,
        "integration_name": integration_name
    }
```

#### statuses_mappings
```python
elif table_name == "statuses_mappings":
    workflow_step_name = ""
    workflow_step_number = None
    if entity.workflow:
        workflow_step_name = entity.workflow.step_name or ""
        workflow_step_number = entity.workflow.step_number
    
    integration_name = ""
    if entity.integration:
        integration_name = entity.integration.provider or ""
    
    return {
        "status_from": entity.status_from or "",
        "status_to": entity.status_to or "",
        "status_category": entity.status_category or "",
        "workflow_step_name": workflow_step_name,
        "workflow_step_number": workflow_step_number or 0,
        "integration_name": integration_name
    }
```

#### workflows
```python
elif table_name == "workflows":
    integration_name = ""
    if entity.integration:
        integration_name = entity.integration.provider or ""
    
    return {
        "step_name": entity.step_name or "",
        "step_number": entity.step_number or 0,
        "step_category": entity.step_category or "",
        "is_commitment_point": entity.is_commitment_point or False,
        "integration_name": integration_name
    }
```

### 5. Fixed Table Name Normalization

**File**: `services/backend-service/app/etl/vectorization.py`

Added normalization to handle both `status_mappings` (from frontend) and `statuses_mappings` (database table):

```python
# Normalize table name (accept both status_mappings and statuses_mappings)
if table_name == 'status_mappings':
    table_name = 'statuses_mappings'

# Validate table name
valid_tables = ['wits_hierarchies', 'wits_mappings', 'statuses_mappings', 'workflows']
```

## Architecture Notes

### Mapping Tables Use Internal IDs

Unlike most ETL tables which use `external_id` for vectorization queue messages, mapping tables use internal database IDs because:

1. They are configuration tables, not external data
2. They don't have external IDs from source systems
3. They are created/managed within Health Pulse

### Data Preparation Includes Relationships

The data preparation methods for mapping tables include related entity information:
- Integration name (provider) for all tables
- Hierarchy level and name for WIT mappings
- Workflow step info for status mappings

This enriched data provides better context for AI vectorization and retrieval.

### Source Type Mapping

All four mapping tables are correctly mapped to 'JIRA' source type in `SOURCE_TYPE_MAPPING`:

```python
SOURCE_TYPE_MAPPING = {
    # Jira Agent's scope (all Jira-related data including cross-links)
    'statuses_mappings': 'JIRA',
    'workflows': 'JIRA',
    'wits_hierarchies': 'JIRA',
    'wits_mappings': 'JIRA',
    # ... other tables
}
```

## Testing

To test the fix:

1. Navigate to any mapping page in ETL frontend:
   - WITs Hierarchies (`/etl/wits-hierarchies`)
   - WITs Mappings (`/etl/wits-mappings`)
   - Status Mappings (`/etl/statuses-mappings`)
   - Workflows (`/etl/workflows`)

2. Click "Queue for Vectorization" button

3. Verify:
   - Success message shows number of records queued
   - No errors in backend-service logs
   - VectorizationWorker processes messages successfully
   - Vectors are stored in Qdrant
   - Bridge records created in `qdrant_vectors` table

## Files Modified

1. `services/backend-service/app/workers/vectorization_worker.py`
   - Added model imports
   - Updated TABLE_MODEL_MAP
   - Updated _fetch_entity method
   - Added _prepare_entity_data methods for all 4 mapping tables

2. `services/backend-service/app/etl/vectorization.py`
   - Added table name normalization for status_mappings/statuses_mappings
   - Updated valid_tables list
   - Updated table_model_map

## Related Memory

This fix aligns with the existing memory:
> "Mapping tables (WIT hierarchies, WIT mappings, status mappings, workflows) should use entity_type 'jira_mappings' for vectorization queue, with worker vectorizing all table data"

Note: The implementation uses individual table names rather than a single 'jira_mappings' entity_type, which provides better granularity for vectorization and retrieval.

