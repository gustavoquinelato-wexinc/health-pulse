# Custom Fields Mapping Architecture - Simplified Implementation

## Overview

This document describes the final implemented architecture for custom fields mapping in the ETL system. The implementation uses a simplified direct FK approach instead of the originally planned complex UI-driven configuration system.

## Architecture Decision

**Original Plan**: Complex UI-driven system with project-specific discovery and drag-drop mapping interface.

**Final Implementation**: Simplified direct FK mapping with global custom fields extraction.

### Why the Change?

1. **Jira Reality**: Custom fields in Jira are global, not project-specific
2. **Complexity Reduction**: Direct FK relationships are simpler and more maintainable
3. **Performance**: Fewer joins and lookups during ETL processing
4. **Tenant Isolation**: Clean separation per tenant/integration

## Database Schema

### custom_fields Table (Global)
```sql
CREATE TABLE custom_fields (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(100) NOT NULL,     -- 'customfield_10001'
    name VARCHAR(255) NOT NULL,            -- 'Agile Team'
    field_type VARCHAR(100) NOT NULL,      -- 'team', 'string', 'option'
    operations JSONB DEFAULT '[]',         -- ['set'], ['add', 'remove']
    integration_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, integration_id, external_id)
);
```

### custom_fields_mappings Table (Tenant Configuration)
```sql
CREATE TABLE custom_fields_mappings (
    id SERIAL PRIMARY KEY,

    -- 20 direct FK columns to custom_fields
    custom_field_01_id INTEGER REFERENCES custom_fields(id),
    custom_field_02_id INTEGER REFERENCES custom_fields(id),
    custom_field_03_id INTEGER REFERENCES custom_fields(id),
    -- ... (17 more columns)
    custom_field_20_id INTEGER REFERENCES custom_fields(id),

    integration_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, integration_id)
);
```

## ETL Processing Flow

### 1. Custom Fields Sync (Extract)
```python
# Extract all custom fields globally from Jira createmeta API
def sync_custom_fields():
    # 1. Call Jira createmeta API
    # 2. Store raw response in raw_extraction_data
    # 3. Queue transform message
```

### 2. Transform Worker Processing
```python
def process_jira_custom_fields():
    # 1. Get raw createmeta data
    # 2. Collect all unique custom fields globally (not per project)
    # 3. Process each unique custom field once
    # 4. Bulk insert/update custom_fields table
```

### 3. Work Items Processing
```python
def process_work_items():
    # 1. Get custom_fields_mappings for tenant/integration
    # 2. For each work item, map custom field values using FK relationships
    # 3. Store in work_items.custom_field_01 through custom_field_20
```

## Key Benefits

1. **Simplicity**: Direct FK relationships, no complex JSON configurations
2. **Performance**: Fast lookups using database indexes
3. **Maintainability**: Standard database relationships
4. **Tenant Isolation**: Clean separation per tenant/integration
5. **Deduplication**: Each custom field processed only once globally

## Implementation Status

- ✅ Database schema created
- ✅ Models updated with FK relationships
- ✅ Transform worker updated with global deduplication
- ✅ Bulk operations with conflict handling
- ✅ Column name consistency (last_updated_at)
- ✅ JSONB type handling for operations field

## Future Enhancements

1. **UI Configuration**: Admin interface to configure custom_fields_mappings
2. **Auto-mapping**: Intelligent suggestions based on field names
3. **Validation**: Ensure mapped fields exist and are active
4. **Overflow Handling**: JSON overflow for fields beyond 20 columns

## Migration Notes

- Old complex architecture was never fully implemented
- New simplified approach is production-ready
- No data migration needed (fresh implementation)
- Documentation updated to reflect new architecture
