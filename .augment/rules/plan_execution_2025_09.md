---
type: "manual"
---

# Plan Execution Rule: plan_execution_2025_09

## 📋 Rule Definition

**Trigger**: When user provides a plan document for execution
**Purpose**: Systematically execute plan documents, track progress, and maintain documentation

## 🎯 Rule Process

### **Step 1: Task List Cleanup**
- Review current task list using `view_tasklist`
- Remove completed, cancelled, or irrelevant tasks
- Clean up task hierarchy for new plan execution

### **Step 2: Plan Analysis & Task Breakdown**
- Read and analyze the provided plan document
- Break down the plan into actionable tasks with proper hierarchy
- Ensure each task represents meaningful work (~20 minutes for a professional developer)
- Create clear task descriptions with acceptance criteria

### **Step 3: Task List Population**
- Use `add_tasks` to create the task hierarchy
- Set appropriate task states (NOT_STARTED, IN_PROGRESS, COMPLETE)ARTED for new tasks)
- Establish proper parent-child relationships for subtasks
- Organize tasks in logical execution order

### **Step 4: Systematic Task Execution**
- Execute tasks in order using `update_tasks` to track progress
- Mark current task as IN_PROGRESS when starting
- Mark completed tasks as COMPLETE when finished
- Use batch updates for efficiency: `{"tasks": [{"task_id": "prev", "state": "COMPLETE"}, {"task_id": "current", "state": "IN_PROGRESS"}]}`

### **Step 5: Plan Document Update**
- Mark the original plan document as `**Implemented**: YES ✅`
- Update any status indicators in the document
- Preserve all original content and structure

### **Step 6: File Organization**
- Move the completed plan document to `/completed` subfolder in the same directory
- Create `/completed` folder if it doesn't exist
- Maintain original filename and structure
- Example: `docs/evolution_plans/ai/plan.md` → `docs/evolution_plans/ai/completed/plan.md`

### **Step 7: Documentation Update**
- Update `/docs/reports/report_2025_09.md` with new capabilities
- Add the implemented features to appropriate sections
- Update status indicators and metrics
- Maintain professional report format

## 🔄 Multi-Folder Support

This rule works with any folder structure:
- `docs/evolution_plans/ai/plan.md` → `docs/evolution_plans/ai/completed/plan.md`
- `docs/features/ui/plan.md` → `docs/features/ui/completed/plan.md`
- `projects/backend/plan.md` → `projects/backend/completed/plan.md`

## ✅ Success Criteria

1. **Task Management**: All plan items converted to trackable tasks
2. **Execution**: All tasks completed systematically with progress tracking
3. **Documentation**: Plan marked as implemented and moved to `/completed`
4. **Reporting**: `/docs/reports/report_2025_09.md` updated with new capabilities
5. **Organization**: Clean task list and proper file organization maintained

## 🎯 Usage

**Trigger Phrase**: "Use plan_execution_2025_09 rule" or when user provides a plan document
**Expected Input**: Path to plan document or plan document content
**Expected Output**: Fully executed plan with updated documentation

## 📝 Example Workflow

```
User: "Execute this plan: docs/features/new_feature.md"

Agent:
1. Clean up task list
2. Break down new_feature.md into tasks
3. Add tasks to task management system
4. Execute tasks systematically
5. Mark docs/features/new_feature.md as "Implemented: YES ✅"
6. Move to docs/features/completed/new_feature.md
7. Update docs/reports/report_2025_09.md
```

## 🔧 Tools Used

- `view_tasklist` - Review current tasks
- `add_tasks` - Create new task hierarchy
- `update_tasks` - Track progress and mark completion
- `str-replace-editor` - Update plan documents
- `save-file` - Create files if needed
- `view` - Read plan documents and verify changes

## 📊 Tracking

This rule ensures:
- **Accountability**: Every plan execution is tracked and documented
- **Progress Visibility**: Clear task progression and completion status
- **Documentation**: Comprehensive reporting of implemented capabilities
- **Organization**: Clean file structure with completed plans archived
- **Repeatability**: Consistent process for any plan document

---

**Rule Status**: ACTIVE ✅
**Created**: August 2025
**Last Updated**: August 2025
