# ETL Phase 2.1: Jira Database Foundation & UI Management

**Implemented**: NO ❌
**Duration**: 1 week (Week 5 of overall plan)
**Priority**: CRITICAL
**Risk Level**: LOW
**Last Updated**: 2025-10-02

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
   - RabbitMQ container running
   - Database tables created (`raw_extraction_data`, `etl_job_queue`)
   - Queue manager implemented in backend-service
   - Raw data APIs functional

**Status**: Ready to start after Phase 1 completion.

## 💼 Business Outcome

**Database Foundation & UI for Custom Fields**: Create the database schema and user interface needed for dynamic Jira custom field management:
- **Database tables** for custom field discovery and mapping
- **JSON overflow column** for unlimited custom fields
- **UI pages** for custom field mapping and discovery
- **Model updates** across all services

This creates the foundation for UI-driven custom field configuration.

## 🎯 Objectives

1. **Database Schema**: Add custom field management tables and overflow column
2. **Model Updates**: Update unified models across all services (etl-service, backend-service)
3. **UI Development**: Create custom field mapping and discovery pages
4. **Integration**: Connect UI to backend APIs for configuration management

## 📋 Task Breakdown

### Task 2.1.1: Database Schema Enhancement
**Duration**: 2 days
**Priority**: CRITICAL

#### Migration 0001 Updates
```sql
-- services/backend-service/scripts/migrations/0001_initial_db_schema.py

# Add to existing work_items table
ALTER TABLE work_items ADD COLUMN custom_fields_overflow JSONB;

# Create GIN index for JSON queries
CREATE INDEX idx_work_items_custom_fields_overflow_gin 
ON work_items USING GIN (custom_fields_overflow);

# Custom field mappings (stored in integrations table)
ALTER TABLE integrations ADD COLUMN custom_field_mappings JSONB;

# NOTE: projects_custom_fields and projects_issue_types tables removed
# Custom field discovery is now handled via API calls without database storage
# This simplifies the architecture and reduces database complexity

# Indexes for performance
CREATE INDEX idx_projects_custom_fields_project_id ON projects_custom_fields(project_id);
CREATE INDEX idx_projects_custom_fields_integration_id ON projects_custom_fields(integration_id);
CREATE INDEX idx_projects_custom_fields_tenant_id ON projects_custom_fields(tenant_id);
CREATE INDEX idx_projects_custom_fields_jira_field_id ON projects_custom_fields(jira_field_id);

CREATE INDEX idx_projects_issue_types_project_id ON projects_issue_types(project_id);
CREATE INDEX idx_projects_issue_types_integration_id ON projects_issue_types(integration_id);
CREATE INDEX idx_projects_issue_types_tenant_id ON projects_issue_types(tenant_id);

CREATE INDEX idx_integrations_custom_field_mappings_gin ON integrations USING GIN (custom_field_mappings);
```

### Task 2.1.2: Model Updates Across Services
**Duration**: 1 day
**Priority**: HIGH

#### Backend Service Models
```python
# services/backend-service/app/models/work_items.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSONB
from sqlalchemy.ext.declarative import declarative_base

class WorkItem(Base):
    __tablename__ = 'work_items'
    
    # ... existing fields ...
    
    # NEW: Custom fields overflow
    custom_fields_overflow = Column(JSONB, nullable=True)

# NOTE: ProjectCustomField and ProjectIssueType models removed
# Custom field discovery is now handled via API calls without database storage

# services/backend-service/app/models/integrations.py
class Integration(Base):
    __tablename__ = 'integrations'
    
    # ... existing fields ...
    
    # NEW: Custom field mappings
    custom_field_mappings = Column(JSONB, nullable=True)
```

#### ETL Service Models
```python
# services/etl-service/app/models/work_items.py
class WorkItem(Base):
    __tablename__ = 'work_items'
    
    # ... existing fields ...
    
    # NEW: Custom fields overflow
    custom_fields_overflow = Column(JSONB, nullable=True)
```

### Task 2.1.3: Custom Fields Mapping UI Page
**Duration**: 2 days
**Priority**: HIGH

#### Custom Fields Mapping Page
```typescript
// services/etl-frontend/src/pages/CustomFieldsMapping.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Save, RefreshCw, Eye } from 'lucide-react';

interface CustomFieldMapping {
  [key: string]: string; // custom_field_01: "customfield_10110"
}

interface DiscoveredField {
  jira_field_id: string;
  jira_field_name: string;
  jira_field_type: string;
  project_count: number;
}

export const CustomFieldsMapping: React.FC = () => {
  const [mappings, setMappings] = useState<CustomFieldMapping>({});
  const [discoveredFields, setDiscoveredFields] = useState<DiscoveredField[]>([]);
  const [selectedIntegration, setSelectedIntegration] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Generate 20 custom field slots
  const customFieldSlots = Array.from({ length: 20 }, (_, i) => 
    `custom_field_${(i + 1).toString().padStart(2, '0')}`
  );

  useEffect(() => {
    if (selectedIntegration) {
      loadMappings();
      loadDiscoveredFields();
    }
  }, [selectedIntegration]);

  const loadMappings = async () => {
    try {
      const response = await fetch(`/api/v1/etl/integrations/${selectedIntegration}/custom-field-mappings`);
      const data = await response.json();
      setMappings(data.custom_field_mappings || {});
    } catch (error) {
      console.error('Failed to load mappings:', error);
    }
  };

  const loadDiscoveredFields = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/v1/etl/integrations/${selectedIntegration}/discovered-custom-fields`);
      const data = await response.json();
      setDiscoveredFields(data.fields || []);
    } catch (error) {
      console.error('Failed to load discovered fields:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMappingChange = (slot: string, fieldId: string) => {
    setMappings(prev => ({
      ...prev,
      [slot]: fieldId || undefined
    }));
  };

  const saveMappings = async () => {
    setIsSaving(true);
    try {
      await fetch(`/api/v1/etl/integrations/${selectedIntegration}/custom-field-mappings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_field_mappings: mappings })
      });
      
      // Show success message
      alert('Custom field mappings saved successfully!');
    } catch (error) {
      console.error('Failed to save mappings:', error);
      alert('Failed to save mappings. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const getUsedFields = () => {
    return new Set(Object.values(mappings).filter(Boolean));
  };

  const getAvailableFields = () => {
    const usedFields = getUsedFields();
    return discoveredFields.filter(field => !usedFields.has(field.jira_field_id));
  };

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-primary">Custom Fields Mapping</h1>
        <p className="text-secondary mt-2">
          Configure which Jira custom fields map to the 20 available custom columns.
          Unmapped fields will be stored in JSON overflow.
        </p>
      </div>

      {/* Integration Selection */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Select Integration</CardTitle>
        </CardHeader>
        <CardContent>
          <Select value={selectedIntegration?.toString()} onValueChange={(value) => setSelectedIntegration(parseInt(value))}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a Jira integration" />
            </SelectTrigger>
            <SelectContent>
              {/* This would be populated from integrations API */}
              <SelectItem value="1">Jira Production</SelectItem>
              <SelectItem value="2">Jira Staging</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {selectedIntegration && (
        <>
          {/* Mapping Configuration */}
          <Card className="mb-6">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Field Mappings</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" onClick={loadDiscoveredFields} disabled={isLoading}>
                  <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                  Refresh Fields
                </Button>
                <Button onClick={saveMappings} disabled={isSaving}>
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? 'Saving...' : 'Save Mappings'}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {customFieldSlots.map((slot) => (
                  <div key={slot} className="space-y-2">
                    <Label htmlFor={slot} className="text-sm font-medium">
                      {slot.replace('_', ' ').toUpperCase()}
                    </Label>
                    <Select 
                      value={mappings[slot] || ''} 
                      onValueChange={(value) => handleMappingChange(slot, value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select field..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">-- None --</SelectItem>
                        {getAvailableFields().map((field) => (
                          <SelectItem key={field.jira_field_id} value={field.jira_field_id}>
                            <div className="flex flex-col">
                              <span className="font-medium">{field.jira_field_name}</span>
                              <span className="text-xs text-gray-500">{field.jira_field_id}</span>
                            </div>
                          </SelectItem>
                        ))}
                        {/* Show currently selected field even if it would be filtered out */}
                        {mappings[slot] && !getAvailableFields().find(f => f.jira_field_id === mappings[slot]) && (
                          <SelectItem value={mappings[slot]}>
                            <span className="text-orange-600">{mappings[slot]} (current)</span>
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Discovered Fields Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Discovered Custom Fields</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex gap-4 text-sm text-gray-600">
                  <span>Total discovered: {discoveredFields.length}</span>
                  <span>Mapped: {Object.values(mappings).filter(Boolean).length}</span>
                  <span>Unmapped: {discoveredFields.length - Object.values(mappings).filter(Boolean).length}</span>
                </div>
                
                <div className="flex flex-wrap gap-2 mt-4">
                  {discoveredFields.slice(0, 10).map((field) => (
                    <Badge 
                      key={field.jira_field_id} 
                      variant={getUsedFields().has(field.jira_field_id) ? "default" : "secondary"}
                      className="text-xs"
                    >
                      {field.jira_field_name}
                    </Badge>
                  ))}
                  {discoveredFields.length > 10 && (
                    <Badge variant="outline" className="text-xs">
                      +{discoveredFields.length - 10} more
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};
```

### Task 2.1.4: Custom Fields Discovery UI Page
**Duration**: 2 days
**Priority**: MEDIUM

#### Custom Fields Discovery Page
```typescript
// services/etl-frontend/src/pages/CustomFieldsDiscovery.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Search, RefreshCw, Play, Eye } from 'lucide-react';

interface DiscoveredField {
  id: number;
  jira_field_id: string;
  jira_field_name: string;
  jira_field_type: string;
  project_name: string;
  discovered_at: string;
  last_seen_at: string;
  is_active: boolean;
}

export const CustomFieldsDiscovery: React.FC = () => {
  const [fields, setFields] = useState<DiscoveredField[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [selectedIntegration, setSelectedIntegration] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const loadDiscoveredFields = async () => {
    if (!selectedIntegration) return;
    
    setIsLoading(true);
    try {
      const response = await fetch(`/api/v1/etl/integrations/${selectedIntegration}/discovered-custom-fields/detailed`);
      const data = await response.json();
      setFields(data.fields || []);
    } catch (error) {
      console.error('Failed to load discovered fields:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerDiscovery = async () => {
    if (!selectedIntegration) return;
    
    setIsDiscovering(true);
    try {
      await fetch(`/api/v1/etl/integrations/${selectedIntegration}/trigger-discovery`, {
        method: 'POST'
      });
      
      // Reload fields after discovery
      setTimeout(() => {
        loadDiscoveredFields();
        setIsDiscovering(false);
      }, 5000);
      
    } catch (error) {
      console.error('Failed to trigger discovery:', error);
      setIsDiscovering(false);
    }
  };

  const filteredFields = fields.filter(field =>
    field.jira_field_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    field.jira_field_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    field.project_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-primary">Custom Fields Discovery</h1>
        <p className="text-secondary mt-2">
          Discover and manage custom fields from Jira projects using the createmeta API.
        </p>
      </div>

      {/* Controls */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Discovery Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Button 
              onClick={triggerDiscovery} 
              disabled={isDiscovering || !selectedIntegration}
              className="flex items-center gap-2"
            >
              <Play className={`h-4 w-4 ${isDiscovering ? 'animate-spin' : ''}`} />
              {isDiscovering ? 'Discovering...' : 'Run Discovery'}
            </Button>
            
            <Button 
              variant="outline" 
              onClick={loadDiscoveredFields} 
              disabled={isLoading || !selectedIntegration}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
          
          <div className="flex gap-4 items-center">
            <input
              type="text"
              placeholder="Search fields..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="px-3 py-2 border rounded-md flex-1"
            />
            <Badge variant="outline">
              {filteredFields.length} fields
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Discovered Fields Table */}
      <Card>
        <CardHeader>
          <CardTitle>Discovered Custom Fields</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field Name</TableHead>
                <TableHead>Field ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Project</TableHead>
                <TableHead>Discovered</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredFields.map((field) => (
                <TableRow key={field.id}>
                  <TableCell className="font-medium">{field.jira_field_name}</TableCell>
                  <TableCell className="font-mono text-sm">{field.jira_field_id}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{field.jira_field_type}</Badge>
                  </TableCell>
                  <TableCell>{field.project_name}</TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {new Date(field.discovered_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant={field.is_active ? "default" : "secondary"}>
                      {field.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};
```

## ✅ Success Criteria

1. **Database Schema**: All new tables and columns created successfully
2. **Model Updates**: Unified models updated across all services
3. **UI Functionality**: Custom field mapping page working end-to-end
4. **Discovery UI**: Custom field discovery page functional
5. **API Integration**: Frontend connected to backend APIs for configuration

## 🚨 Risk Mitigation

1. **Migration Safety**: Test migration on development database first
2. **Model Consistency**: Ensure all services have matching model definitions
3. **UI Performance**: Optimize field selection dropdowns for large field counts
4. **Data Validation**: Validate custom field mappings before saving
5. **Backward Compatibility**: Ensure existing work_items data remains intact

## 📋 Implementation Checklist

- [ ] Update migration 0001 with new tables and columns
- [ ] Update WorkItem model in backend-service
- [ ] Update WorkItem model in etl-service
- [ ] Create ProjectCustomField and ProjectIssueType models
- [ ] Update Integration model with custom_field_mappings
- [ ] Create custom fields mapping UI page
- [ ] Create custom fields discovery UI page
- [ ] Add navigation links to new pages
- [ ] Create backend API endpoints for custom field management
- [ ] Test UI functionality end-to-end
- [ ] Validate database schema and indexes

## 🔄 Next Steps

After completion, this enables:
- **Phase 2.2**: Enhanced Extraction with Discovery
- **UI-driven configuration**: Users can map custom fields without code changes
- **Foundation ready**: Database and UI ready for dynamic custom field processing

**Mark as Implemented**: ✅ when all checklist items are complete and UI is functional.
