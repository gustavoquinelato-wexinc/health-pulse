# ETL Progress System

## Overview

The ETL system uses a **flexible equal-step progress system** where each job can define any number of steps, and the progress is automatically divided equally among them. This creates a consistent, predictable user experience across all jobs.

## Core Principles

### 1. **Equal Visual Weight**
- Each step gets equal percentage allocation
- No more disproportionate progress (like 5% vs 50% steps)
- Consistent user perception of progress

### 2. **Flexible Step Count**
- Jobs can have any number of steps (1, 5, 10, 42, etc.)
- System automatically calculates: `step_percentage = 100% ÷ total_steps`
- No configuration needed - defined in code per job

### 3. **Predictable Progression**
- Users know exactly what to expect
- Each step represents equal work visually
- Smooth transitions between steps

## Current Job Configurations

### JIRA Job - 5 Steps (20% each)
```
Step 1: 0% → 20%   - Extract Projects and Issue Types
Step 2: 20% → 40%  - Extract Projects and Statuses  
Step 3: 40% → 60%  - Fetch Issues from API (fixed at 60% - unknown total)
Step 4: 60% → 80%  - Process Issues and Changelogs
Step 5: 80% → 100% - Extract Dev Status and Create PR Links
```

### GitHub Job - 3 Steps (33.33% each)
```
Step 1: 0% → 33%   - Setup and Discovery
Step 2: 33% → 67%  - Repository Processing
Step 3: 67% → 100% - Finalization and Cleanup
```

### Vectorization Job - 4 Steps (25% each)
```
Step 1: 0% → 25%   - Initialization and Queue Stats
Step 2: 25% → 50%  - Queue Preparation and Backend Startup
Step 3: 50% → 75%  - Processing Start and Monitoring
Step 4: 75% → 100% - Processing Completion and Cleanup
```

## Technical Implementation

### WebSocket Manager

The `WebSocketManager` provides a new method for step-aware progress updates:

```python
async def send_step_progress_update(
    self, 
    job_name: str, 
    step_index: int,           # 0-based step index
    total_steps: int,          # Total number of steps
    step_progress: Optional[float],  # 0.0-1.0 within step, None for fixed completion
    step_message: str          # Progress message
):
    # Automatically calculates overall percentage
    step_percentage = 100.0 / total_steps
    step_start = step_index * step_percentage
    
    if step_progress is not None:
        # Smooth progression within step
        overall_percentage = step_start + (step_progress * step_percentage)
    else:
        # Fixed completion of current step
        overall_percentage = (step_index + 1) * step_percentage
```

### Usage Examples

#### Within-Step Progression (Known Totals)
```python
# Processing 150 out of 500 items in step 3 of 5
await websocket_manager.send_step_progress_update(
    "Jira", 2, 5, 0.3,  # 30% through step 3
    "Processing issues: 150/500 (30%)"
)
# Results in: 40% + (0.3 × 20%) = 46% overall
```

#### Fixed Step Completion (Unknown Totals)
```python
# Jira fetching completed (step 3 of 5)
await websocket_manager.send_step_progress_update(
    "Jira", 2, 5, None,  # Fixed completion
    "[FETCHED] Fetched 1000 issues"
)
# Results in: 60% overall (step 3 completion)
```

## Special Cases

### Unknown Totals (Jira Fetching)
When the total count is unknown (like Jira API fetching), the step shows **fixed completion** at the step boundary:
- Step 3 fetching always shows 60% when complete
- Provides visual progress without misleading percentages
- User sees meaningful advancement (20% gain)

### Smooth Progression (Known Totals)
When totals are known, progress smoothly advances within the step range:
- Processing 500 items: 0% → 100% within step percentage range
- Real-time updates every N items processed
- Linear progression through step boundaries

## Benefits

### For Users
- ✅ **Predictable Progress**: Each step = equal visual advancement
- ✅ **No Stalled Feeling**: Major operations get proper representation
- ✅ **Consistent Experience**: Same logic across all jobs
- ✅ **Clear Expectations**: Know what each percentage means

### For Developers
- ✅ **Flexible System**: Any number of steps supported
- ✅ **No Configuration**: Define steps in code, system handles math
- ✅ **Maintainable**: Easy to add/remove steps
- ✅ **Scalable**: Works for simple (3 steps) to complex (20+ steps) jobs

## Migration Notes

### Backward Compatibility
- Existing `send_progress_update()` calls still work
- New `send_step_progress_update()` is additive
- Gradual migration possible

### Converting Existing Jobs
1. **Count major steps** in your job workflow
2. **Define TOTAL_STEPS** constant
3. **Replace progress calls** with step-aware versions
4. **Test step boundaries** match expected percentages

## Future Enhancements

### Potential Features
- **Weighted Steps**: Some steps could be larger than others
- **Dynamic Steps**: Step count could change based on data
- **Nested Steps**: Sub-steps within major steps
- **Progress Estimation**: ML-based time estimation per step

### Current Limitations
- All steps must be equal percentage
- Step count must be known at job start
- No sub-step visualization in UI
