# ETL Phase 2.3: Jira Transform & Load Processing

**Implemented**: NO ❌
**Duration**: 1 week (Week 7 of overall plan)
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-02

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 2.1 Complete**: Database Foundation & UI Management
2. ✅ **Phase 2.2 Complete**: Enhanced Extraction with Discovery
   - Discovery job extracting project metadata
   - Enhanced issues extraction with dynamic fields
   - etl_jobs table integration working
   - Raw data being stored in raw_extraction_data table

**Status**: Cannot start until Phase 2.2 is complete.

## 💼 Business Outcome

**Queue-Based Transform & Load with Dynamic Custom Fields**: Implement the Transform and Load phases of the ETL pipeline that:
- **Processes raw Jira data** from extraction queue
- **Applies dynamic custom field mapping** based on UI configuration
- **Stores data efficiently** with 20 optimized columns + JSON overflow
- **Handles discovery data** to update custom field and issue type tables
- **Provides real-time progress** tracking through etl_jobs table

This completes the end-to-end Jira ETL pipeline with dynamic custom field support.

## 🎯 Objectives

1. **Transform Workers**: Process raw Jira data with dynamic custom field mapping
2. **Load Workers**: Store transformed data in final tables efficiently
3. **Discovery Processing**: Update custom field and issue type tables
4. **Progress Tracking**: Real-time job progress and status updates
5. **Error Handling**: Robust error handling and retry mechanisms

## 📋 Task Breakdown

### Task 2.3.1: Jira Transform Worker Implementation
**Duration**: 3 days
**Priority**: CRITICAL

#### Transform Worker for Jira Data
```python
# services/backend-service/app/etl/workers/jira_transform_worker.py
from typing import Dict, Any, List
from app.etl.workers.base_worker import BaseQueueWorker
from app.core.database import get_database_connection
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class JiraTransformWorker(BaseQueueWorker):
    """Transform raw Jira data with dynamic custom field mapping"""
    
    def __init__(self):
        super().__init__('etl.transform.jira')
        self.db = get_database_connection()
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process Jira transformation job"""
        
        raw_data_ids = message.get('raw_data_ids', [])
        entity_type = message.get('entity_type')
        tenant_id = message.get('tenant_id')
        
        logger.info(f"Processing {len(raw_data_ids)} raw records for entity type: {entity_type}")
        
        if entity_type == 'jira_discovery':
            return await self.process_discovery_data(raw_data_ids, tenant_id)
        elif entity_type == 'jira_issues':
            return await self.process_issues_data(raw_data_ids, tenant_id)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
    
    async def process_discovery_data(self, raw_data_ids: List[int], tenant_id: int) -> Dict[str, Any]:
        """Process discovery data to update custom fields and issue types tables"""
        
        processed_count = 0
        
        for raw_data_id in raw_data_ids:
            try:
                # Get raw discovery data
                raw_record = await self.get_raw_data(raw_data_id)
                discovery_data = raw_record['raw_data']
                
                # Update custom fields table
                await self.update_custom_fields_table(discovery_data, tenant_id)
                
                # Update issue types table
                await self.update_issue_types_table(discovery_data, tenant_id)
                
                # Mark raw data as processed
                await self.mark_raw_data_processed(raw_data_id)
                
                processed_count += 1
                logger.info(f"Processed discovery data for project {discovery_data.get('project_key')}")
                
            except Exception as e:
                logger.error(f"Failed to process discovery data {raw_data_id}: {e}")
                await self.mark_raw_data_failed(raw_data_id, str(e))
                continue
        
        return {
            'success': True,
            'processed_count': processed_count,
            'entity_type': 'jira_discovery'
        }
    
    async def update_custom_fields_table(self, discovery_data: Dict, tenant_id: int):
        """Update projects_custom_fields table with discovered fields"""
        
        project_id = discovery_data['project_id']
        integration_id = discovery_data.get('integration_id')
        custom_fields = discovery_data.get('custom_fields', [])
        
        for field in custom_fields:
            try:
                # Upsert custom field record
                await self.db.execute("""
                    INSERT INTO projects_custom_fields (
                        project_id, integration_id, jira_field_id, jira_field_name,
                        jira_field_type, jira_field_schema, discovered_at, last_seen_at,
                        is_active, tenant_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW(), true, $7)
                    ON CONFLICT (project_id, jira_field_id, tenant_id)
                    DO UPDATE SET
                        jira_field_name = EXCLUDED.jira_field_name,
                        jira_field_type = EXCLUDED.jira_field_type,
                        jira_field_schema = EXCLUDED.jira_field_schema,
                        last_seen_at = NOW(),
                        is_active = true
                """,
                    project_id, integration_id, field['jira_field_id'],
                    field['jira_field_name'], field['jira_field_type'],
                    field['jira_field_schema'], tenant_id
                )
                
            except Exception as e:
                logger.error(f"Failed to update custom field {field['jira_field_id']}: {e}")
                continue
    
    async def update_issue_types_table(self, discovery_data: Dict, tenant_id: int):
        """Update projects_issue_types table with discovered issue types"""
        
        project_id = discovery_data['project_id']
        integration_id = discovery_data.get('integration_id')
        issue_types = discovery_data.get('issue_types', [])
        
        for issuetype in issue_types:
            try:
                # Upsert issue type record
                await self.db.execute("""
                    INSERT INTO projects_issue_types (
                        project_id, integration_id, jira_issuetype_id, jira_issuetype_name,
                        jira_issuetype_description, hierarchy_level, is_subtask,
                        discovered_at, last_seen_at, is_active, tenant_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW(), true, $8)
                    ON CONFLICT (project_id, jira_issuetype_id, tenant_id)
                    DO UPDATE SET
                        jira_issuetype_name = EXCLUDED.jira_issuetype_name,
                        jira_issuetype_description = EXCLUDED.jira_issuetype_description,
                        hierarchy_level = EXCLUDED.hierarchy_level,
                        is_subtask = EXCLUDED.is_subtask,
                        last_seen_at = NOW(),
                        is_active = true
                """,
                    project_id, integration_id, issuetype['jira_issuetype_id'],
                    issuetype['jira_issuetype_name'], issuetype['jira_issuetype_description'],
                    issuetype['hierarchy_level'], issuetype['is_subtask'], tenant_id
                )
                
            except Exception as e:
                logger.error(f"Failed to update issue type {issuetype['jira_issuetype_id']}: {e}")
                continue
    
    async def process_issues_data(self, raw_data_ids: List[int], tenant_id: int) -> Dict[str, Any]:
        """Transform raw Jira issues to work_items format"""
        
        processed_count = 0
        
        for raw_data_id in raw_data_ids:
            try:
                # Get raw data
                raw_record = await self.get_raw_data(raw_data_id)
                issue_data = raw_record['raw_data']
                integration_id = raw_record['integration_id']
                
                # Get project ID from issue data
                project_id = self.extract_project_id(issue_data)
                
                # Get custom field mappings for this integration
                field_mappings = await self.get_custom_field_mappings(integration_id)
                
                # Transform issue with dynamic custom fields
                transformed_data = await self.transform_issue(issue_data, field_mappings, integration_id, tenant_id)
                
                # Queue for loading
                await self.queue_for_loading(transformed_data, raw_data_id)
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to transform issue data {raw_data_id}: {e}")
                await self.mark_raw_data_failed(raw_data_id, str(e))
                continue
        
        return {
            'success': True,
            'processed_count': processed_count,
            'entity_type': 'jira_issues'
        }
    
    async def transform_issue(self, issue_data: Dict, field_mappings: Dict, integration_id: int, tenant_id: int) -> Dict[str, Any]:
        """Transform issue with dynamic custom field mapping"""
        
        fields = issue_data.get('fields', {})
        
        # Base transformation (existing logic)
        transformed = {
            'external_id': issue_data.get('id'),
            'key': issue_data.get('key'),
            'summary': fields.get('summary'),
            'description': self.extract_description(fields.get('description')),
            'acceptance_criteria': fields.get('customfield_10222'),  # Keep hardcoded for now
            'created': self.parse_datetime(fields.get('created')),
            'updated': self.parse_datetime(fields.get('updated')),
            'priority': self.extract_priority(fields.get('priority')),
            'resolution': self.extract_resolution(fields.get('resolution')),
            'labels': fields.get('labels') if fields.get('labels') else None,
            'story_points': fields.get('customfield_10024'),
            'team': self.extract_team(fields.get('customfield_10128')),
            'assignee': self.extract_assignee(fields.get('assignee')),
            'project_id': self.extract_project_id(issue_data),
            'wit_id': self.extract_wit_id(fields.get('issuetype')),
            'status_id': self.extract_status_id(fields.get('status')),
            'parent_external_id': self.extract_parent_id(fields.get('parent')),
            'code_changed': True if fields.get('customfield_10000', '') != "{}" else False,
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }
        
        # Process custom fields dynamically
        custom_fields_result = self.process_custom_fields(fields, field_mappings)
        transformed.update(custom_fields_result)
        
        return transformed
    
    def process_custom_fields(self, fields: Dict, field_mappings: Dict) -> Dict[str, Any]:
        """Process custom fields with dynamic mapping"""
        
        result = {}
        overflow = {}
        
        # Process all custom fields from Jira
        for field_key, field_value in fields.items():
            if not field_key.startswith('customfield_'):
                continue
            
            # Skip null values
            if field_value is None:
                continue
            
            # Check if mapped to a column
            mapped_column = None
            for column, mapped_field_id in field_mappings.items():
                if mapped_field_id == field_key:
                    mapped_column = column
                    break
            
            if mapped_column:
                # Store in dedicated column
                result[mapped_column] = self.serialize_value(field_value)
            else:
                # Store in overflow JSON (exclude already mapped fields)
                overflow[field_key] = field_value
        
        # Set overflow (excluding mapped fields)
        if overflow:
            result['custom_fields_overflow'] = overflow
        
        return result
    
    def serialize_value(self, value: Any) -> str:
        """Serialize complex Jira field values to string"""
        
        if value is None:
            return None
        elif isinstance(value, str):
            return value
        elif isinstance(value, dict):
            # Handle objects like {value: "text", id: "123"}
            if 'value' in value:
                return value['value']
            else:
                return str(value)
        elif isinstance(value, list):
            # Handle arrays
            if value and isinstance(value[0], dict) and 'value' in value[0]:
                return ', '.join([item['value'] for item in value if 'value' in item])
            else:
                return ', '.join([str(item) for item in value])
        else:
            return str(value)
    
    async def get_custom_field_mappings(self, integration_id: int) -> Dict[str, str]:
        """Get custom field mappings from integrations table"""
        
        result = await self.db.fetchrow("""
            SELECT custom_field_mappings 
            FROM integrations 
            WHERE id = $1
        """, integration_id)
        
        if result and result['custom_field_mappings']:
            return result['custom_field_mappings']
        else:
            return {}
```

### Task 2.3.2: Jira Load Worker Implementation
**Duration**: 2 days
**Priority**: HIGH

#### Load Worker for Final Tables
```python
# services/backend-service/app/etl/workers/jira_load_worker.py
class JiraLoadWorker(BaseQueueWorker):
    """Load transformed Jira data to final tables"""
    
    def __init__(self):
        super().__init__('etl.load.jira')
        self.db = get_database_connection()
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Load transformed data to work_items table"""
        
        transformed_data_ids = message.get('transformed_data_ids', [])
        entity_type = message.get('entity_type')
        
        logger.info(f"Loading {len(transformed_data_ids)} transformed records for {entity_type}")
        
        loaded_count = 0
        
        for data_id in transformed_data_ids:
            try:
                # Get transformed data
                transformed_record = await self.get_transformed_data(data_id)
                work_item_data = transformed_record['transformed_data']
                
                # Upsert to work_items table
                await self.upsert_work_item(work_item_data)
                
                # Queue for vectorization
                await self.queue_for_vectorization(work_item_data)
                
                # Mark transformed data as loaded
                await self.mark_transformed_data_loaded(data_id)
                
                loaded_count += 1
                
            except Exception as e:
                logger.error(f"Failed to load transformed data {data_id}: {e}")
                await self.mark_transformed_data_failed(data_id, str(e))
                continue
        
        return {
            'success': True,
            'loaded_count': loaded_count,
            'entity_type': entity_type
        }
    
    async def upsert_work_item(self, work_item_data: Dict[str, Any]):
        """Upsert work item to work_items table with dynamic custom fields"""
        
        try:
            # Build dynamic SQL for custom fields
            custom_field_columns = []
            custom_field_values = []
            custom_field_updates = []
            
            # Handle custom_field_01 through custom_field_20
            for i in range(1, 21):
                field_name = f'custom_field_{i:02d}'
                if field_name in work_item_data:
                    custom_field_columns.append(field_name)
                    custom_field_values.append(work_item_data[field_name])
                    custom_field_updates.append(f"{field_name} = EXCLUDED.{field_name}")
            
            # Handle custom_fields_overflow
            if 'custom_fields_overflow' in work_item_data:
                custom_field_columns.append('custom_fields_overflow')
                custom_field_values.append(work_item_data['custom_fields_overflow'])
                custom_field_updates.append('custom_fields_overflow = EXCLUDED.custom_fields_overflow')
            
            # Build base columns and values
            base_columns = [
                'external_id', 'key', 'summary', 'description', 'acceptance_criteria',
                'created', 'updated', 'priority', 'resolution', 'labels', 'story_points',
                'team', 'assignee', 'project_id', 'wit_id', 'status_id', 'parent_external_id',
                'code_changed', 'integration_id', 'tenant_id'
            ]
            
            base_values = [
                work_item_data.get('external_id'),
                work_item_data.get('key'),
                work_item_data.get('summary'),
                work_item_data.get('description'),
                work_item_data.get('acceptance_criteria'),
                work_item_data.get('created'),
                work_item_data.get('updated'),
                work_item_data.get('priority'),
                work_item_data.get('resolution'),
                work_item_data.get('labels'),
                work_item_data.get('story_points'),
                work_item_data.get('team'),
                work_item_data.get('assignee'),
                work_item_data.get('project_id'),
                work_item_data.get('wit_id'),
                work_item_data.get('status_id'),
                work_item_data.get('parent_external_id'),
                work_item_data.get('code_changed'),
                work_item_data.get('integration_id'),
                work_item_data.get('tenant_id')
            ]
            
            # Combine columns and values
            all_columns = base_columns + custom_field_columns
            all_values = base_values + custom_field_values
            
            # Build placeholders
            placeholders = ', '.join([f'${i+1}' for i in range(len(all_values))])
            
            # Build update clause
            base_updates = [
                'summary = EXCLUDED.summary',
                'description = EXCLUDED.description',
                'acceptance_criteria = EXCLUDED.acceptance_criteria',
                'updated = EXCLUDED.updated',
                'priority = EXCLUDED.priority',
                'resolution = EXCLUDED.resolution',
                'labels = EXCLUDED.labels',
                'story_points = EXCLUDED.story_points',
                'team = EXCLUDED.team',
                'assignee = EXCLUDED.assignee',
                'status_id = EXCLUDED.status_id',
                'parent_external_id = EXCLUDED.parent_external_id',
                'code_changed = EXCLUDED.code_changed',
                'last_updated_at = NOW()'
            ]
            
            all_updates = base_updates + custom_field_updates
            
            # Execute upsert
            sql = f"""
                INSERT INTO work_items ({', '.join(all_columns)})
                VALUES ({placeholders})
                ON CONFLICT (external_id, tenant_id)
                DO UPDATE SET {', '.join(all_updates)}
                RETURNING id
            """
            
            result = await self.db.fetchrow(sql, *all_values)
            
            logger.debug(f"Upserted work item {work_item_data.get('key')} with ID {result['id']}")
            
        except Exception as e:
            logger.error(f"Failed to upsert work item {work_item_data.get('key')}: {e}")
            raise
    
    async def queue_for_vectorization(self, work_item_data: Dict[str, Any]):
        """Queue work item for vectorization"""
        
        try:
            # Add to vectorization queue
            await self.db.execute("""
                INSERT INTO vectorization_queue (
                    table_name, external_id, operation, entity_data, tenant_id
                ) VALUES ('work_items', $1, 'upsert', $2, $3)
                ON CONFLICT (table_name, external_id, operation, tenant_id)
                DO UPDATE SET
                    entity_data = EXCLUDED.entity_data,
                    created_at = NOW()
            """,
                work_item_data.get('external_id'),
                work_item_data,
                work_item_data.get('tenant_id')
            )
            
        except Exception as e:
            logger.error(f"Failed to queue for vectorization: {e}")
            # Don't fail the load operation for vectorization errors
```

### Task 2.3.3: Job Progress Tracking Enhancement
**Duration**: 2 days
**Priority**: MEDIUM

#### Real-time Progress Updates
```python
# services/backend-service/app/etl/core/job_progress_tracker.py
class JobProgressTracker:
    """Track job progress in etl_jobs table with real-time updates"""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.db = get_database_connection()
    
    async def start_job(self, job_name: str, total_items: int = None):
        """Mark job as started"""
        
        checkpoint_data = {
            'total_items': total_items,
            'processed_items': 0,
            'current_stage': 'starting',
            'stages': {
                'extract': {'status': 'pending', 'progress': 0},
                'transform': {'status': 'pending', 'progress': 0},
                'load': {'status': 'pending', 'progress': 0}
            }
        }
        
        await self.db.execute("""
            UPDATE etl_jobs 
            SET 
                status = 'RUNNING',
                progress_percentage = 0,
                checkpoint_data = $1,
                last_run_started_at = NOW(),
                error_message = NULL,
                retry_count = 0
            WHERE job_name = $2 AND tenant_id = $3
        """, checkpoint_data, job_name, self.tenant_id)
    
    async def update_stage_progress(self, job_name: str, stage: str, progress: int, processed_items: int = None):
        """Update progress for a specific stage"""
        
        # Get current checkpoint data
        current_job = await self.db.fetchrow("""
            SELECT checkpoint_data FROM etl_jobs 
            WHERE job_name = $1 AND tenant_id = $2
        """, job_name, self.tenant_id)
        
        if current_job and current_job['checkpoint_data']:
            checkpoint_data = current_job['checkpoint_data']
        else:
            checkpoint_data = {'stages': {}}
        
        # Update stage progress
        if 'stages' not in checkpoint_data:
            checkpoint_data['stages'] = {}
        
        checkpoint_data['stages'][stage] = {
            'status': 'running' if progress < 100 else 'completed',
            'progress': progress
        }
        
        if processed_items is not None:
            checkpoint_data['processed_items'] = processed_items
        
        checkpoint_data['current_stage'] = stage
        
        # Calculate overall progress
        overall_progress = self.calculate_overall_progress(checkpoint_data['stages'])
        
        await self.db.execute("""
            UPDATE etl_jobs 
            SET 
                progress_percentage = $1,
                checkpoint_data = $2,
                last_updated_at = NOW()
            WHERE job_name = $3 AND tenant_id = $4
        """, overall_progress, checkpoint_data, job_name, self.tenant_id)
    
    def calculate_overall_progress(self, stages: Dict) -> int:
        """Calculate overall progress from stage progress"""
        
        stage_weights = {
            'extract': 0.3,    # 30%
            'transform': 0.4,  # 40%
            'load': 0.3        # 30%
        }
        
        total_progress = 0
        for stage, weight in stage_weights.items():
            if stage in stages:
                stage_progress = stages[stage].get('progress', 0)
                total_progress += (stage_progress * weight)
        
        return int(total_progress)
    
    async def complete_job(self, job_name: str, success: bool = True, error_message: str = None):
        """Mark job as completed or failed"""
        
        status = 'COMPLETED' if success else 'FAILED'
        progress = 100 if success else 0
        
        await self.db.execute("""
            UPDATE etl_jobs 
            SET 
                status = $1,
                progress_percentage = $2,
                error_message = $3,
                last_run_finished_at = NOW(),
                last_updated_at = NOW()
            WHERE job_name = $4 AND tenant_id = $5
        """, status, progress, error_message, job_name, self.tenant_id)
```

## ✅ Success Criteria

1. **Transform Workers**: Raw Jira data processed with dynamic custom field mapping
2. **Load Workers**: Transformed data stored efficiently in work_items table
3. **Discovery Processing**: Custom field and issue type tables updated correctly
4. **Progress Tracking**: Real-time job progress visible in UI
5. **Error Handling**: Robust error handling with proper retry mechanisms

## 🚨 Risk Mitigation

1. **Data Integrity**: Validate transformed data before loading
2. **Performance**: Monitor queue processing times and optimize bottlenecks
3. **Error Recovery**: Implement proper retry logic for failed transformations
4. **Memory Usage**: Handle large batches efficiently to avoid memory issues
5. **Database Locks**: Optimize upsert operations to minimize lock contention

## 📋 Implementation Checklist

- [ ] Implement Jira transform worker with dynamic custom field processing
- [ ] Implement Jira load worker with efficient upserts
- [ ] Add discovery data processing for custom fields and issue types
- [ ] Implement job progress tracking with real-time updates
- [ ] Add error handling and retry mechanisms
- [ ] Test transform worker with UI-configured mappings
- [ ] Test load worker with custom fields overflow
- [ ] Validate discovery data processing
- [ ] Test end-to-end pipeline from extraction to loading
- [ ] Performance test with large data volumes

## 🔄 Next Steps

After completion, this enables:
- **Complete Jira ETL Pipeline**: End-to-end processing with dynamic custom fields
- **Phase 3**: GitHub Enhancement with queue integration
- **Production Deployment**: Full Jira ETL with UI-driven custom field management

**Mark as Implemented**: ✅ when all checklist items are complete and end-to-end pipeline is working successfully.
