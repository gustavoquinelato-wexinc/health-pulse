# Custom Fields Page - Restore Mapping Functionality

**Date**: 2025-10-11  
**Component**: ETL Frontend - Custom Fields Page

## Overview

Restored the full custom field mapping functionality to the Custom Fields page, allowing users to map 20 work_items table columns to Jira custom fields. Also removed the page header (title/subtitle) to match other mapping pages.

## Changes Made

### 1. Restored State Variables

**Added back**:
```typescript
const [fieldMappings, setFieldMappings] = useState<FieldMappingState>({});
const [saving, setSaving] = useState(false);
```

**Interface**:
```typescript
interface FieldMappingState {
  [key: string]: number | null; // e.g., { "custom_field_01": 123, "custom_field_02": null, ... }
}
```

### 2. Restored Functions

**Added back**:
- `loadMappingConfig(integrationId)` - Loads saved mappings from backend
- `saveMappingConfig()` - Saves mappings to backend
- `updateFieldMapping(fieldKey, customFieldId)` - Updates mapping state when user changes dropdown

### 3. Updated useEffect Hooks

**Restored mapping loading**:
```typescript
useEffect(() => {
  if (integrations.length > 0 && !selectedIntegration) {
    const jiraIntegration = integrations[0];
    setSelectedIntegration(jiraIntegration.id);
    loadCustomFields(jiraIntegration.id);
    loadMappingConfig(jiraIntegration.id);  // ← Restored
  }
}, [integrations]);

useEffect(() => {
  if (selectedIntegration) {
    loadCustomFields(selectedIntegration);
    loadMappingConfig(selectedIntegration);  // ← Restored
  }
}, [selectedIntegration]);
```

### 4. Removed Page Header

**Removed**:
```tsx
{/* Page Header */}
<div className="mb-8">
  <div className="flex items-center justify-between mb-6">
    <div>
      <h1 className="text-3xl font-bold text-primary">
        Custom Fields
      </h1>
      <p className="text-lg text-secondary">
        Sync custom fields from Jira using the createmeta API to discover available custom fields.
      </p>
    </div>
  </div>
</div>
```

### 5. Updated Action Buttons

**Changed from single button to two buttons**:
```tsx
<div className="mb-6 flex justify-end space-x-3">
  {/* Sync from Jira Button */}
  <button onClick={syncCustomFields} disabled={syncing} ...>
    <Download className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
    <span>{syncing ? 'Syncing from Jira...' : 'Sync from Jira'}</span>
  </button>
  
  {/* Save Mappings Button */}
  <button onClick={saveMappingConfig} disabled={saving} ...>
    <Save className="h-4 w-4" />
    <span>{saving ? 'Saving...' : 'Save Mappings'}</span>
  </button>
</div>
```

### 6. Restored Mapping Table

**Changed from simple list to full mapping table**:

**Before** (Simple List):
- Showed only discovered custom fields
- 3 columns: Field Name, Field Type, Jira Field ID
- Read-only display

**After** (Mapping Table):
- Shows 20 rows for work_items columns (custom_field_01 through custom_field_20)
- 4 columns: Work Items Column, Jira Custom Field, Field Type, Jira Field ID
- Dropdown selectors to map each column to a Jira custom field
- Shows selected field's type and ID when mapped

## Table Structure

### Work Items Columns (20 rows)

Each row represents a column in the `work_items` table:
- `custom_field_01`
- `custom_field_02`
- ...
- `custom_field_20`

### Mapping Dropdowns

Each row has a dropdown with:
- "-- Not Mapped --" (default)
- All discovered Jira custom fields (from `custom_fields` table)

When a field is selected:
- The mapping is stored in state
- Field Type and Jira Field ID are displayed
- User can click "Save Mappings" to persist to database

## User Workflow

1. **Sync from Jira**
   - Click "Sync from Jira" button
   - System calls Jira createmeta API
   - Discovers custom fields from Jira projects
   - Stores in `custom_fields` table
   - Populates dropdown options

2. **Map Fields**
   - For each work_items column (01-20)
   - Select a Jira custom field from dropdown
   - See field type and ID displayed
   - Repeat for all needed mappings

3. **Save Mappings**
   - Click "Save Mappings" button
   - Mappings saved to database
   - Success toast notification

4. **ETL Job Uses Mappings**
   - When ETL job runs
   - Reads mapping configuration
   - Extracts data from mapped Jira custom fields
   - Stores in corresponding work_items columns

## Page Layout (After Changes)

```
┌─────────────────────────────────────────────────────────┐
│                    [Sync from Jira] [Save Mappings]     │  ← Action buttons
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ Custom Field Mappings                                   │  ← Table header
│ Map Jira custom fields to work_items table columns...  │
├─────────────────────────────────────────────────────────┤
│ Work Items Column | Jira Custom Field | Type | ID      │
├─────────────────────────────────────────────────────────┤
│ 01 Custom Field 01│ [Dropdown]        │ ...  │ ...     │
│ 02 Custom Field 02│ [Dropdown]        │ ...  │ ...     │
│ ...               │ ...               │ ...  │ ...     │
│ 20 Custom Field 20│ [Dropdown]        │ ...  │ ...     │
└─────────────────────────────────────────────────────────┘
```

## Backend Integration

### API Endpoints Used

1. **GET `/custom-fields/list/{integration_id}`**
   - Lists discovered custom fields from database
   - Populates dropdown options

2. **POST `/custom-fields/sync/{integration_id}`**
   - Syncs custom fields from Jira createmeta API
   - Stores in `custom_fields` table

3. **GET `/custom-fields/mappings-table/{integration_id}`**
   - Loads saved mapping configuration
   - Returns `{ "custom_field_01": 123, "custom_field_02": 456, ... }`

4. **PUT `/custom-fields/mappings-table/{integration_id}`**
   - Saves mapping configuration
   - Stores which custom_fields.id maps to which work_items column

## Database Schema

### custom_fields Table
- Stores discovered Jira custom fields
- Columns: id, integration_id, name, external_id, field_type, etc.

### Mapping Configuration
- Stored in database (exact table TBD by backend implementation)
- Maps work_items column names to custom_fields.id
- Example: `{ "custom_field_01": 123, "custom_field_05": 456 }`

### work_items Table
- Has 20 dedicated custom field columns:
  - `custom_field_01` through `custom_field_20`
- ETL job populates these based on mapping configuration

## Files Modified

1. `services/etl-frontend/src/pages/CustomFieldMappingPage.tsx`
   - Restored state variables: `fieldMappings`, `saving`
   - Restored functions: `loadMappingConfig`, `saveMappingConfig`, `updateFieldMapping`
   - Removed page header (title/subtitle)
   - Added "Save Mappings" button
   - Restored full mapping table (20 rows with dropdowns)

## Imports Added

```typescript
import { Loader2, Download, FileText, Save } from 'lucide-react';
```

Added `Save` icon for the "Save Mappings" button.

## Testing

To test the restored functionality:

1. **Navigate to Custom Fields page**
   - Verify no title/subtitle at top
   - Verify two buttons: "Sync from Jira" and "Save Mappings"

2. **Sync Custom Fields**
   - Click "Sync from Jira"
   - Verify spinner shows
   - Verify success toast
   - Verify dropdowns populate with custom fields

3. **Map Fields**
   - Select a custom field from dropdown for custom_field_01
   - Verify field type and ID appear in row
   - Select fields for other rows
   - Verify selections persist in UI

4. **Save Mappings**
   - Click "Save Mappings"
   - Verify "Saving..." text shows
   - Verify success toast
   - Refresh page
   - Verify mappings are still selected (loaded from database)

5. **Empty State**
   - Clear all custom fields from database
   - Verify "No Custom Fields Found" message
   - Verify prompt to sync from Jira

## Benefits

✅ **Full Functionality Restored** - Users can map custom fields again  
✅ **Consistent Layout** - Matches other mapping pages (no header)  
✅ **Clear Workflow** - Sync → Map → Save  
✅ **20 Columns Available** - Supports up to 20 custom fields  
✅ **Persistent Mappings** - Saved to database  
✅ **ETL Integration** - Jobs use mappings to extract data

