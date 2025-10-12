# Button Spinner Animations

**Date**: 2025-10-11  
**Component**: ETL Frontend - All Mapping Pages

## Overview

Added spinning animations to all action buttons ("Queue for Vectorization" and "Sync from Jira") to provide visual feedback when operations are in progress.

## Changes Made

### 1. WITs Hierarchies Page (`WitsHierarchiesPage.tsx`)

**State Added**:
```typescript
const [queueing, setQueueing] = useState(false)
```

**Handler Updated**:
```typescript
const handleQueueForVectorization = async () => {
  try {
    setQueueing(true)  // Start spinner
    // ... API call ...
  } catch (err) {
    // ... error handling ...
  } finally {
    setQueueing(false)  // Stop spinner
  }
}
```

**Button Updated**:
```tsx
<button
  onClick={handleQueueForVectorization}
  disabled={queueing}
  className="... disabled:opacity-50"
  style={{ background: 'var(--gradient-1-2)' }}
>
  {queueing ? (
    <Loader2 className="h-4 w-4 animate-spin" />
  ) : (
    <svg>...</svg>  // Original icon
  )}
  <span>{queueing ? 'Queueing...' : 'Queue for Vectorization'}</span>
</button>
```

### 2. WITs Mappings Page (`WitsMappingsPage.tsx`)

**Same pattern as above**:
- Added `queueing` state
- Updated `handleQueueForVectorization` with try/finally
- Updated button with spinner and "Queueing..." text

### 3. Status Mappings Page (`StatusesMappingsPage.tsx`)

**Same pattern as above**:
- Added `queueing` state
- Updated `handleQueueForVectorization` with try/finally
- Updated button with spinner and "Queueing..." text

### 4. Workflows Page (`WorkflowsPage.tsx`)

**Same pattern as above**:
- Added `queueing` state
- Updated `handleQueueForVectorization` with try/finally
- Updated button with spinner and "Queueing..." text

### 5. Custom Fields Page (`CustomFieldMappingPage.tsx`)

**Already had spinner** - The "Sync from Jira" button already had:
- `syncing` state
- Spinner animation with `<Download className={syncing ? 'animate-spin' : ''} />`
- "Syncing from Jira..." text when active

## Visual Behavior

### Before Click
```
[📦 Icon] Queue for Vectorization
```

### During Operation
```
[⟳ Spinning] Queueing...
```
- Button is disabled (50% opacity)
- Icon changes to spinning Loader2
- Text changes to "Queueing..."
- User cannot click again

### After Completion
```
[📦 Icon] Queue for Vectorization
```
- Button re-enabled
- Original icon restored
- Original text restored

## User Experience Improvements

1. **Visual Feedback**: Users immediately see the button is working
2. **Prevent Double-Clicks**: Button is disabled during operation
3. **Clear Status**: Text changes to indicate ongoing operation
4. **Consistent Pattern**: All mapping pages use the same spinner behavior
5. **Professional Feel**: Smooth animation matches modern UI standards

## Technical Details

### Spinner Icon
- Uses `Loader2` from `lucide-react` (already imported)
- Size: `h-4 w-4` (16x16px, matching original icon)
- Animation: `animate-spin` (Tailwind CSS built-in)

### Button States
- **Normal**: Full opacity, clickable
- **Queueing**: 50% opacity (`disabled:opacity-50`), not clickable
- **Hover**: 90% opacity (when not disabled)

### State Management
- State set to `true` at start of async operation
- State set to `false` in `finally` block (ensures cleanup even on error)
- Button disabled when state is `true`

## Files Modified

1. `services/etl-frontend/src/pages/WitsHierarchiesPage.tsx`
2. `services/etl-frontend/src/pages/WitsMappingsPage.tsx`
3. `services/etl-frontend/src/pages/StatusesMappingsPage.tsx`
4. `services/etl-frontend/src/pages/WorkflowsPage.tsx`
5. `services/etl-frontend/src/pages/CustomFieldMappingPage.tsx` (already had spinner)

## Testing

To test the spinner animations:

1. Navigate to any mapping page (Hierarchies, Mappings, Status Mappings, Workflows)
2. Click "Queue for Vectorization" button
3. Verify:
   - Button shows spinning icon immediately
   - Text changes to "Queueing..."
   - Button is disabled (grayed out)
   - Cannot click button again while queueing
4. Wait for operation to complete
5. Verify:
   - Button returns to normal state
   - Original icon restored
   - Original text restored
   - Button is clickable again

For Custom Fields page:
1. Navigate to Custom Fields page
2. Click "Sync from Jira" button
3. Verify same spinner behavior with "Syncing from Jira..." text

## Code Pattern

This pattern can be reused for any async button action:

```typescript
// 1. Add state
const [loading, setLoading] = useState(false)

// 2. Wrap async handler
const handleAction = async () => {
  try {
    setLoading(true)
    // ... async operation ...
  } catch (err) {
    // ... error handling ...
  } finally {
    setLoading(false)
  }
}

// 3. Update button
<button
  onClick={handleAction}
  disabled={loading}
  className="... disabled:opacity-50"
>
  {loading ? (
    <Loader2 className="h-4 w-4 animate-spin" />
  ) : (
    <OriginalIcon className="h-4 w-4" />
  )}
  <span>{loading ? 'Loading...' : 'Original Text'}</span>
</button>
```

## Benefits

✅ **Better UX**: Users know the system is working  
✅ **Prevent Errors**: Can't trigger duplicate operations  
✅ **Professional**: Matches modern web app standards  
✅ **Consistent**: Same pattern across all pages  
✅ **Accessible**: Disabled state prevents interaction  
✅ **Reliable**: `finally` block ensures cleanup

