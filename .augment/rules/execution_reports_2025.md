---
type: "manual"
---

# Execution Reports Rule: execution_reports_2025

## 📋 Rule Definition

**Trigger**: When user provides a plan document for execution or requests plan execution
**Purpose**: Systematically execute plan documents, track progress, and maintain monthly documentation reports

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
- Set appropriate task states (NOT_STARTED for new tasks)
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

### **Step 7: Monthly Report Update**
- Check `/docs/reports/` directory for existing monthly reports
- Determine current month (YYYY_MM format)
- If current month report exists, update it; otherwise create new one based on previous month's template
- Update the monthly report with new capabilities and implementations
- Add implemented features to appropriate sections
- Update status indicators and metrics
- Maintain professional report format

## 📅 Monthly Report Management

### **Report Naming Convention**
- Format: `report_YYYY_MM.md` (e.g., `report_2025_10.md`)
- Location: `/docs/reports/`

### **Report Creation Logic**
1. **Check existing reports**: Look for current month report first
2. **If current month exists**: Update existing report
3. **If current month missing**: 
   - Find most recent previous month report
   - Copy structure and format from previous month
   - Create new report for current month
   - Update content with current month's implementations

### **Report Structure Template**
```markdown
# Monthly Development Report - YYYY-MM

## 🎯 Executive Summary
## 🚀 Major Implementations
## 🔧 Technical Improvements
## 📊 Metrics & Performance
## 🔄 Architecture Updates
## 🛡️ Security Enhancements
## 📚 Documentation Updates
## 🧪 Testing & Quality
## 🔮 Next Month Priorities
```

## 🔄 Multi-Folder Support

This rule works with any folder structure:
- `docs/evolution_plans/ai/plan.md` → `docs/evolution_plans/ai/completed/plan.md`
- `docs/features/ui/plan.md` → `docs/features/ui/completed/plan.md`
- `projects/backend/plan.md` → `projects/backend/completed/plan.md`

## ✅ Success Criteria

1. **Task Management**: All plan items converted to trackable tasks
2. **Execution**: All tasks completed systematically with progress tracking
3. **Documentation**: Plan marked as implemented and moved to `/completed`
4. **Reporting**: Current month's report updated with new capabilities
5. **Organization**: Clean task list and proper file organization maintained

## 🎯 Usage

**Trigger Phrases**: 
- "Use execution_reports_2025 rule"
- "Execute this plan"
- "Implement plan document"
- When user provides a plan document

**Expected Input**: Path to plan document or plan document content
**Expected Output**: Fully executed plan with updated monthly documentation

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
7. Check for /docs/reports/report_2025_10.md
8. If exists: Update report_2025_10.md
9. If missing: Create from report_2025_09.md template
```

## 🔧 Tools Used

- `view_tasklist` - Review current tasks
- `add_tasks` - Create new task hierarchy
- `update_tasks` - Track progress and mark completion
- `str-replace-editor` - Update plan documents and reports
- `save-file` - Create new monthly reports
- `view` - Read plan documents, reports, and verify changes

## 📊 Tracking

This rule ensures:
- **Accountability**: Every plan execution is tracked and documented
- **Progress Visibility**: Clear task progression and completion status
- **Monthly Documentation**: Comprehensive reporting of implemented capabilities
- **Organization**: Clean file structure with completed plans archived
- **Repeatability**: Consistent process for any plan document
- **Historical Record**: Monthly reports provide development timeline

---

**Rule Status**: ACTIVE ✅
**Created**: October 2025
**Last Updated**: October 2025
**Replaces**: plan_execution_2025_09.md
