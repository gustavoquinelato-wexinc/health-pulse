# Custom Fields Page Simplification

**Date**: 2025-10-11  
**Component**: ETL Frontend - Custom Fields Page

## Changes Made

Simplified the Custom Fields page to remove the configuration/mapping section and keep only the "Sync from Jira" functionality with a clean list view of discovered fields.

## What Was Removed

1. **Jira Custom Fields Configuration Card**
   - Removed the large card with integration logo and details
   - Removed the old "Sync from Jira" button embedded in the card

2. **Custom Field Mappings Table**
   - Removed the 20-row mapping table (custom_field_01 through custom_field_20)
   - Removed dropdown selectors for mapping Jira fields to work_items columns
   - Removed "Save Mappings" button and functionality
   - Removed all mapping-related state and functions

3. **Unused Code**
   - Removed `fieldMappings` state variable
   - Removed `saving` state variable
   - Removed `loadMappingConfig()` function
   - Removed `saveMappingConfig()` function
   - Removed `updateFieldMapping()` function
   - Removed unused imports: `Sliders`, `Save`, `IntegrationLogo`

## What Was Added/Updated

1. **Simplified Header**
   - Updated description: "Sync custom fields from Jira using the createmeta API to discover available custom fields."

2. **New Sync Button**
   - Positioned at top-right, matching other mapping pages
   - Uses `var(--gradient-1-2)` gradient styling (consistent with Queue for Vectorization buttons)
   - Hover effect with opacity change
   - Shows spinner animation when syncing

3. **Simplified Custom Fields List**
   - Changed from "Custom Field Mappings" to "Discovered Custom Fields"
   - Removed "Work Items Column" column
   - Shows only:
     - Field Name
     - Field Type
     - Jira Field ID
   - Clean, read-only display of discovered fields

## UI Consistency

The page now follows the same pattern as other mapping pages:

**WITs Hierarchies Page**:
- Header with description
- "Queue for Vectorization" button (top-right, gradient-1-2)
- Table of hierarchies

**Custom Fields Page** (after changes):
- Header with description
- "Sync from Jira" button (top-right, gradient-1-2)
- Table of discovered fields

## Button Styling

```tsx
<button
  onClick={syncCustomFields}
  disabled={syncing}
  className="px-4 py-2 rounded-lg text-white flex items-center space-x-2 transition-colors disabled:opacity-50"
  style={{ background: 'var(--gradient-1-2)' }}
  onMouseEnter={(e) => {
    e.currentTarget.style.opacity = '0.9'
  }}
  onMouseLeave={(e) => {
    e.currentTarget.style.opacity = '1'
  }}
>
  <Download className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
  <span>{syncing ? 'Syncing from Jira...' : 'Sync from Jira'}</span>
</button>
```

## Functionality Preserved

✅ **Sync from Jira** - Calls `/custom-fields/sync/{integration_id}` endpoint  
✅ **List Custom Fields** - Displays discovered fields from database  
✅ **Auto-select Integration** - Automatically selects first Jira integration  
✅ **Loading States** - Shows loading spinner while fetching data  
✅ **Error Handling** - Toast notifications for success/error  
✅ **Empty State** - Shows helpful message when no fields are discovered

## Functionality Removed

❌ **Field Mapping Configuration** - No longer allows mapping fields to custom_field_01-20 columns  
❌ **Save Mappings** - No longer saves mapping configuration to database  
❌ **Mapping State Management** - No longer tracks which fields are mapped to which columns

## Backend Impact

**No backend changes required**. The page still uses:
- `GET /custom-fields/list/{integration_id}` - List discovered fields
- `POST /custom-fields/sync/{integration_id}` - Sync from Jira

The following endpoints are no longer called from this page:
- `GET /custom-fields/mappings-table/{integration_id}` - Get mappings
- `PUT /custom-fields/mappings-table/{integration_id}` - Save mappings

These endpoints can remain in the backend for potential future use or other integrations.

## Files Modified

1. **services/etl-frontend/src/pages/CustomFieldMappingPage.tsx**
   - Removed configuration card and mapping table
   - Added simplified sync button
   - Removed unused state variables and functions
   - Cleaned up imports

## Testing

To test the changes:

1. Navigate to Custom Fields page in ETL frontend
2. Verify "Sync from Jira" button appears at top-right with gradient styling
3. Click "Sync from Jira"
4. Verify sync starts and shows "Syncing from Jira..." with spinner
5. Verify success toast appears when sync completes
6. Verify discovered fields appear in table with:
   - Field Name
   - Field Type
   - Jira Field ID
7. Verify empty state shows when no fields are discovered

## Visual Comparison

**Before**:
- Large configuration card with integration logo
- Complex 20-row mapping table with dropdowns
- Save Mappings button
- Cluttered UI with multiple actions

**After**:
- Clean header with description
- Simple sync button (matching other pages)
- Read-only list of discovered fields
- Minimal, focused UI

## Rationale

The mapping functionality was removed because:
1. Custom field mapping is complex and may be better handled through a different approach
2. The 20-column limitation may not be sufficient for all use cases
3. Simplifying to just discovery makes the page more focused and easier to use
4. Consistent with the "ice" experience - calm, clean aesthetics
5. Matches the pattern of other mapping pages (hierarchies, mappings, workflows)

