# Workflow Management

This document describes the workflow management system in the Pulse Platform.

## Overview

The workflow management system allows administrators to define workflow steps that represent different stages in their development process. These workflows are used to map external system statuses (like Jira) to standardized workflow stages for analytics and reporting.

## Core Concepts

### Workflow Steps
- **Step Name**: Descriptive name for the workflow stage (e.g., "In Development", "Code Review")
- **Step Number**: Optional ordering number for display purposes
- **Step Category**: Standardized category (To Do, In Progress, Done, Discarded)
- **Integration Assignment**: Associate with specific integration or apply globally

### Commitment Points
- **Purpose**: Mark the initial commitment point for lead time calculation (Kanban principles)
- **Constraint**: Only one commitment point allowed per client/integration combination
- **Analytics**: Used to calculate lead time metrics from commitment to delivery

## Technical Implementation

### Database Schema
```sql
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    step_name VARCHAR NOT NULL,
    step_number INTEGER,
    step_category VARCHAR NOT NULL,
    is_commitment_point BOOLEAN DEFAULT FALSE,
    integration_id INTEGER REFERENCES integrations(id),
    client_id INTEGER NOT NULL REFERENCES clients(id),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- Unique constraint for commitment points
CREATE UNIQUE INDEX idx_unique_commitment_point_per_client_integration 
ON workflows(client_id, integration_id) 
WHERE is_commitment_point = true;
```

### API Endpoints

#### ETL Service (Primary)
- `GET /api/v1/admin/workflows` - List all workflows
- `GET /api/v1/admin/workflows/{id}` - Get workflow details
- `POST /api/v1/admin/workflows` - Create new workflow
- `PUT /api/v1/admin/workflows/{id}` - Update workflow
- `DELETE /api/v1/admin/workflows/{id}` - Delete workflow
- `GET /api/v1/admin/workflows/{id}/dependencies` - Check dependencies

#### Backend Service
- `GET /api/v1/admin/workflows` - List workflows (for frontend integration)
- `GET /api/v1/admin/workflows/{id}` - Get workflow details
- `POST /api/v1/admin/workflows` - Create workflow
- `PUT /api/v1/admin/workflows/{id}` - Update workflow

## Validation Rules

### Commitment Point Validation
1. **Database Level**: Unique partial index prevents multiple commitment points
2. **API Level**: Pre-validation before database operations
3. **Error Messages**: Clear, actionable feedback with context

### Example Validation Logic
```python
if update_data.is_commitment_point:
    existing_commitment_point = session.query(Workflow).filter(
        Workflow.client_id == user.client_id,
        Workflow.integration_id == update_data.integration_id,
        Workflow.is_commitment_point == True,
        Workflow.active == True,
        Workflow.id != workflow_id
    ).first()

    if existing_commitment_point:
        integration_name = get_integration_name(update_data.integration_id)
        raise HTTPException(
            status_code=400,
            detail=f"Only one commitment point is allowed per integration. "
                   f"A commitment point already exists for '{integration_name}': "
                   f"'{existing_commitment_point.step_name}'. "
                   f"Please uncheck the commitment point for the existing workflow first."
        )
```

## Frontend Integration

### Modal Population
```javascript
async function editWorkflow(id) {
    const workflow = await fetchWorkflowDetails(id);
    
    // Always populate dropdowns first
    populateIntegrationDropdown();
    
    // Then set values
    document.getElementById('integration').value = workflow.integration_id || '';
    document.getElementById('workflowCategory').value = workflow.step_category || '';
    // ... other fields
}
```

### Error Handling
```javascript
try {
    const errorData = await response.json();
    alert(`Failed to save workflow: ${errorData.detail || 'Unknown error'}`);
} catch (parseError) {
    const errorText = await response.text();
    alert(`Failed to save workflow: ${errorText}`);
}
```

## Usage Examples

### Creating a Workflow
1. Navigate to ETL Service admin panel → Workflows
2. Click "Add New Workflow"
3. Fill in workflow details:
   - **Name**: "In Development"
   - **Category**: "In Progress"
   - **Integration**: Select specific integration or leave blank for global
   - **Commitment Point**: Check if this is the commitment point for lead time

### Setting Commitment Points
- Only one workflow per integration can be marked as a commitment point
- If you try to set a second commitment point, you'll get a clear error message
- To change commitment points, first uncheck the existing one, then set the new one

### Integration Assignment
- **Specific Integration**: Workflow applies only to that integration
- **No Integration (Global)**: Workflow applies to all integrations
- Each client/integration combination can have its own set of workflows

## Best Practices

1. **Naming**: Use clear, descriptive names that match your team's terminology
2. **Categories**: Stick to the four standard categories for consistent analytics
3. **Commitment Points**: Choose the point where work is truly committed (not just planned)
4. **Integration Assignment**: Use specific integrations when workflows differ between systems
5. **Step Numbers**: Use for display ordering, but don't rely on them for logic

## Troubleshooting

### Common Issues
- **"Only one commitment point allowed"**: Uncheck existing commitment point first
- **Integration dropdown empty**: Check that integrations are active and properly configured
- **Values not showing in edit modal**: Ensure dropdowns are populated before setting values

### Error Messages
All error messages include:
- Clear description of the problem
- Context (integration name, existing workflow name)
- Specific instructions on how to resolve the issue
