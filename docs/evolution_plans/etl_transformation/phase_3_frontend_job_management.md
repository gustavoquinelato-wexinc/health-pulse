# ETL Phase 3: Frontend Job Management

**Implemented**: NO ❌
**Duration**: 1 week (Week 7 of overall plan)
**Priority**: HIGH
**Risk Level**: LOW
**Last Updated**: 2025-09-30

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend with management pages working
2. 🔄 **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
3. 🔄 **Phase 2 Complete**: Extract-only ETL service + Transform/Load workers

**Status**: Cannot start until Phase 1 and Phase 2 are complete.

## 💼 Business Outcome

**Complete Job Management UI**: Create a comprehensive Jobs page in the ETL frontend that allows users to:
- View all ETL jobs (Jira, GitHub, etc.)
- Control job execution (start, pause, stop)
- Monitor real-time progress
- View queue status and metrics
- Access job history and logs

This preserves the UX from the old ETL service while leveraging the new queue-based architecture.

## 🎯 Objectives

1. **Jobs Page Creation**: Build new Jobs management page in etl-frontend
2. **Job Controls**: Implement start/pause/stop/force-pending controls
3. **Real-time Progress**: WebSocket integration for live job updates
4. **Queue Monitoring**: Display queue depth and processing status
5. **UI/UX Preservation**: Match the look and feel of old ETL service home page

## 📋 Task Breakdown

### Task 3.1: API Client Updates
**Duration**: 2 days  
**Priority**: HIGH  

#### Update ETL API Client
```typescript
// services/frontend-app/src/api/etlApi.ts
import { apiClient } from './apiClient';
import { 
  ETLJob, 
  JobStatus, 
  RawDataRecord, 
  ETLPipelineRequest,
  TransformRequest,
  LoadRequest 
} from '../types/etl';

export class ETLApiClient {
  
  // Raw Data Management
  async storeRawData(request: StoreRawDataRequest): Promise<{ record_id: number }> {
    const response = await apiClient.post('/api/v1/etl/raw-data/store', request);
    return response.data;
  }

  async getRawData(entityType: string, status?: string, limit: number = 100): Promise<RawDataRecord[]> {
    const params = new URLSearchParams({
      entity_type: entityType,
      limit: limit.toString()
    });
    
    if (status) {
      params.append('status', status);
    }

    const response = await apiClient.get(`/api/v1/etl/raw-data?${params}`);
    return response.data;
  }

  async updateRawDataStatus(recordId: number, status: string, errorDetails?: any): Promise<void> {
    await apiClient.put(`/api/v1/etl/raw-data/${recordId}/status`, {
      status,
      error_details: errorDetails
    });
  }

  // Pipeline Management
  async triggerETLPipeline(request: ETLPipelineRequest): Promise<{ job_id: string }> {
    const response = await apiClient.post('/api/v1/etl/pipeline/trigger', request);
    return response.data;
  }

  async getJobStatus(jobId: string): Promise<JobStatus> {
    const response = await apiClient.get(`/api/v1/etl/jobs/${jobId}/status`);
    return response.data;
  }

  // Transform Operations
  async triggerTransform(request: TransformRequest): Promise<{ job_id: string }> {
    const response = await apiClient.post('/api/v1/etl/transform/jira-issues', request);
    return response.data;
  }

  // Load Operations
  async triggerLoad(request: LoadRequest): Promise<{ job_id: string }> {
    const response = await apiClient.post('/api/v1/etl/load/work-items', request);
    return response.data;
  }

  // Legacy compatibility - gradually migrate these
  async getJobs(): Promise<ETLJob[]> {
    // Map to new API structure while maintaining compatibility
    const response = await apiClient.get('/api/v1/etl/jobs');
    return response.data.map(this.mapLegacyJob);
  }

  private mapLegacyJob(job: any): ETLJob {
    // Map legacy job structure to new structure
    return {
      id: job.id,
      name: job.name,
      status: job.status,
      progress: job.progress || 0,
      last_run: job.last_run_started_at,
      next_run: job.next_run_at,
      // ... other mappings
    };
  }
}

export const etlApi = new ETLApiClient();
```

#### Update Job Status Types
```typescript
// services/frontend-app/src/types/etl.ts
export interface RawDataRecord {
  id: number;
  entity_type: string;
  external_id?: string;
  raw_data: Record<string, any>;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  processed_at?: string;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  stage: 'extract' | 'transform' | 'load' | 'vectorize';
  started_at?: string;
  completed_at?: string;
  error_details?: Record<string, any>;
  metrics: {
    extracted_count?: number;
    transformed_count?: number;
    loaded_count?: number;
    error_count?: number;
  };
}

export interface ETLPipelineRequest {
  entity_type: string;
  integration_id: number;
  payload: Record<string, any>;
  priority?: number;
}

export interface StoreRawDataRequest {
  integration_id: number;
  entity_type: string;
  external_id?: string;
  raw_data: Record<string, any>;
  extraction_metadata?: Record<string, any>;
}
```

### Task 3.2: Job Dashboard Updates
**Duration**: 3 days  
**Priority**: HIGH  

#### Enhanced Job Cards Component
```tsx
// services/frontend-app/src/components/jobs/JobCard.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Clock, Play, Pause, AlertCircle, CheckCircle } from 'lucide-react';
import { ETLJob, JobStatus } from '@/types/etl';
import { etlApi } from '@/api/etlApi';
import { useWebSocket } from '@/hooks/useWebSocket';

interface JobCardProps {
  job: ETLJob;
  onJobUpdate?: (job: ETLJob) => void;
}

export const JobCard: React.FC<JobCardProps> = ({ job, onJobUpdate }) => {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // WebSocket for real-time updates
  const { lastMessage } = useWebSocket(`/ws/jobs/${job.id}/status`);

  useEffect(() => {
    if (lastMessage) {
      const statusUpdate = JSON.parse(lastMessage.data);
      setJobStatus(statusUpdate);
    }
  }, [lastMessage]);

  const handleTriggerJob = async () => {
    setIsLoading(true);
    try {
      const result = await etlApi.triggerETLPipeline({
        entity_type: job.entity_type,
        integration_id: job.integration_id,
        payload: job.default_payload || {},
        priority: 5
      });

      // Start polling for status updates
      pollJobStatus(result.job_id);
      
    } catch (error) {
      console.error('Failed to trigger job:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const pollJobStatus = async (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await etlApi.getJobStatus(jobId);
        setJobStatus(status);
        
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(interval);
          if (onJobUpdate) {
            onJobUpdate({ ...job, status: status.status });
          }
        }
      } catch (error) {
        console.error('Failed to get job status:', error);
        clearInterval(interval);
      }
    }, 2000);
  };

  const getStatusIcon = () => {
    if (jobStatus) {
      switch (jobStatus.status) {
        case 'running':
          return <Clock className="h-4 w-4 animate-spin" />;
        case 'completed':
          return <CheckCircle className="h-4 w-4 text-green-500" />;
        case 'failed':
          return <AlertCircle className="h-4 w-4 text-red-500" />;
        default:
          return <Clock className="h-4 w-4" />;
      }
    }
    return job.active ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />;
  };

  const getStatusBadge = () => {
    if (jobStatus) {
      const statusColors = {
        pending: 'bg-yellow-100 text-yellow-800',
        running: 'bg-blue-100 text-blue-800',
        completed: 'bg-green-100 text-green-800',
        failed: 'bg-red-100 text-red-800'
      };
      
      return (
        <Badge className={statusColors[jobStatus.status]}>
          {jobStatus.status.toUpperCase()}
        </Badge>
      );
    }
    
    return (
      <Badge variant={job.active ? 'default' : 'secondary'}>
        {job.status?.toUpperCase() || 'READY'}
      </Badge>
    );
  };

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          {getStatusIcon()}
          {job.name}
        </CardTitle>
        {getStatusBadge()}
      </CardHeader>
      
      <CardContent>
        {/* Progress Bar for Running Jobs */}
        {jobStatus?.status === 'running' && (
          <div className="mb-4">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Stage: {jobStatus.stage}</span>
              <span>{jobStatus.progress}%</span>
            </div>
            <Progress value={jobStatus.progress} className="h-2" />
          </div>
        )}

        {/* Job Metrics */}
        {jobStatus?.metrics && (
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 mb-4">
            {jobStatus.metrics.extracted_count && (
              <div>Extracted: {jobStatus.metrics.extracted_count}</div>
            )}
            {jobStatus.metrics.transformed_count && (
              <div>Transformed: {jobStatus.metrics.transformed_count}</div>
            )}
            {jobStatus.metrics.loaded_count && (
              <div>Loaded: {jobStatus.metrics.loaded_count}</div>
            )}
            {jobStatus.metrics.error_count && (
              <div className="text-red-600">Errors: {jobStatus.metrics.error_count}</div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={handleTriggerJob}
            disabled={isLoading || jobStatus?.status === 'running'}
            className="flex-1"
          >
            {isLoading ? 'Starting...' : 'Run Job'}
          </Button>
          
          {jobStatus?.status === 'failed' && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {/* Show error details */}}
            >
              View Errors
            </Button>
          )}
        </div>

        {/* Last Run Info */}
        <div className="text-xs text-gray-500 mt-2">
          {job.last_run && (
            <div>Last run: {new Date(job.last_run).toLocaleString()}</div>
          )}
          {job.next_run && (
            <div>Next run: {new Date(job.next_run).toLocaleString()}</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
```

### Task 3.3: Real-time Progress Enhancement
**Duration**: 2 days  
**Priority**: MEDIUM  

#### WebSocket Hook for Job Updates
```typescript
// services/frontend-app/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState } from 'react';

interface UseWebSocketOptions {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export const useWebSocket = (url: string, options: UseWebSocketOptions = {}) => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const ws = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);

  const {
    onOpen,
    onClose,
    onError,
    reconnectAttempts = 3,
    reconnectInterval = 3000
  } = options;

  const connect = () => {
    try {
      setConnectionStatus('connecting');
      
      // Get auth token for WebSocket connection
      const token = localStorage.getItem('auth_token');
      const wsUrl = `${url}?token=${token}`;
      
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        setConnectionStatus('connected');
        reconnectCount.current = 0;
        onOpen?.();
      };

      ws.current.onmessage = (event) => {
        setLastMessage(event);
      };

      ws.current.onclose = () => {
        setConnectionStatus('disconnected');
        onClose?.();
        
        // Attempt reconnection
        if (reconnectCount.current < reconnectAttempts) {
          reconnectCount.current++;
          setTimeout(connect, reconnectInterval);
        }
      };

      ws.current.onerror = (error) => {
        onError?.(error);
      };

    } catch (error) {
      console.error('WebSocket connection failed:', error);
      setConnectionStatus('disconnected');
    }
  };

  useEffect(() => {
    connect();

    return () => {
      ws.current?.close();
    };
  }, [url]);

  const sendMessage = (message: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(message);
    }
  };

  return {
    lastMessage,
    connectionStatus,
    sendMessage
  };
};
```

### Task 3.4: Error Handling Enhancement
**Duration**: 1 day  
**Priority**: MEDIUM  

#### Error Display Component
```tsx
// services/frontend-app/src/components/jobs/JobErrorModal.tsx
import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AlertCircle, Clock, Database, Network } from 'lucide-react';

interface JobErrorModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobName: string;
  errorDetails: {
    stage: string;
    error_type: string;
    message: string;
    timestamp: string;
    stack_trace?: string;
    context?: Record<string, any>;
  };
}

export const JobErrorModal: React.FC<JobErrorModalProps> = ({
  isOpen,
  onClose,
  jobName,
  errorDetails
}) => {
  const getErrorIcon = (errorType: string) => {
    switch (errorType) {
      case 'connection_error':
        return <Network className="h-4 w-4 text-red-500" />;
      case 'database_error':
        return <Database className="h-4 w-4 text-red-500" />;
      case 'timeout_error':
        return <Clock className="h-4 w-4 text-orange-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getErrorBadgeColor = (stage: string) => {
    const colors = {
      extract: 'bg-blue-100 text-blue-800',
      transform: 'bg-purple-100 text-purple-800',
      load: 'bg-green-100 text-green-800',
      vectorize: 'bg-orange-100 text-orange-800'
    };
    return colors[stage as keyof typeof colors] || 'bg-gray-100 text-gray-800';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {getErrorIcon(errorDetails.error_type)}
            Job Error: {jobName}
          </DialogTitle>
          <DialogDescription>
            Error occurred during {errorDetails.stage} stage at {new Date(errorDetails.timestamp).toLocaleString()}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Error Summary */}
          <div className="flex items-center gap-2">
            <Badge className={getErrorBadgeColor(errorDetails.stage)}>
              {errorDetails.stage.toUpperCase()}
            </Badge>
            <Badge variant="destructive">
              {errorDetails.error_type.replace('_', ' ').toUpperCase()}
            </Badge>
          </div>

          {/* Error Message */}
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h4 className="font-medium text-red-800 mb-2">Error Message</h4>
            <p className="text-red-700">{errorDetails.message}</p>
          </div>

          {/* Context Information */}
          {errorDetails.context && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h4 className="font-medium text-gray-800 mb-2">Context</h4>
              <pre className="text-xs text-gray-600 overflow-x-auto">
                {JSON.stringify(errorDetails.context, null, 2)}
              </pre>
            </div>
          )}

          {/* Stack Trace */}
          {errorDetails.stack_trace && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h4 className="font-medium text-gray-800 mb-2">Stack Trace</h4>
              <ScrollArea className="h-32">
                <pre className="text-xs text-gray-600">
                  {errorDetails.stack_trace}
                </pre>
              </ScrollArea>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
```

## ✅ Success Criteria

1. **API Migration**: All frontend calls use new ETL endpoints
2. **UI/UX Preservation**: No changes to user interface patterns
3. **Real-time Updates**: Enhanced progress tracking with WebSocket
4. **Error Handling**: Improved error display and user feedback
5. **Performance**: Faster job status updates and better responsiveness

## 🚨 Risk Mitigation

1. **API Compatibility**: Maintain backward compatibility during transition
2. **User Experience**: Gradual migration with fallback to legacy APIs
3. **Real-time Performance**: Optimize WebSocket connections and message handling
4. **Error Recovery**: Graceful handling of API failures and network issues
5. **Testing**: Comprehensive testing of all user workflows

## 📋 Implementation Checklist

- [ ] Update ETL API client with new endpoints
- [ ] Migrate job dashboard to use new APIs
- [ ] Enhance job cards with real-time progress
- [ ] Implement WebSocket hook for live updates
- [ ] Add improved error handling and display
- [ ] Update job status types and interfaces
- [ ] Test all user workflows end-to-end
- [ ] Validate real-time updates work correctly
- [ ] Ensure error scenarios are handled gracefully
- [ ] Performance test with multiple concurrent jobs

## 🔄 Next Steps

After completion, this enables:
- **Phase 4**: Testing and production deployment
- **User Training**: Documentation and user guides
- **Monitoring**: Enhanced observability and alerting
