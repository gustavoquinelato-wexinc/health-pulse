# Phase 3-3: Frontend AI Configuration Interface

**Implemented**: NO ❌
**Duration**: 2 days (Days 4-5 of 10)
**Priority**: HIGH
**Dependencies**: Phase 3-2 completion

## 🎯 Objectives

1. **AI Configuration UI**: User-friendly interface for AI model selection and configuration
2. **Multi-Provider Management**: Frontend for managing multiple AI providers (OpenAI, Azure, etc.)
3. **Performance Monitoring**: Real-time AI usage and cost tracking dashboard
4. **Configuration Validation**: Frontend validation of AI provider settings
5. **User Empowerment**: Business users control their AI experience through intuitive interface
6. **WrenAI-Inspired UX**: Clean, professional AI configuration experience

## 🎨 Frontend Architecture

### **AI Configuration Menu Structure**
```
ETL Service Sidebar (Port 8000)
├─ Home
├─ DORA Metrics
├─ Engineering Analytics
├─ Settings
│   ├─ System Settings
│   ├─ User Management
│   └─ AI Configuration ← NEW
│       ├─ AI Providers
│       ├─ Model Selection
│       ├─ Performance Settings
│       ├─ Cost Management
│       └─ Usage Analytics
```

### **AI Configuration Components**

#### **1. AI Provider Management Component**
```typescript
// services/frontend-app/src/components/ai/AIProviderManagement.tsx
import React, { useState, useEffect } from 'react';
import { Card, Form, Select, Input, Button, Switch, Alert, Tabs } from 'antd';
import { CloudOutlined, SettingOutlined, DollarOutlined } from '@ant-design/icons';

interface AIProvider {
  id: number;
  provider_type: string;
  model_name: string;
  integration_name: string;
  active: boolean;
  model_config: any;
  performance_config: any;
  cost_config: any;
}

const AIProviderManagement: React.FC = () => {
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const providerOptions = [
    { value: 'openai', label: 'OpenAI', icon: '🤖' },
    { value: 'azure_openai', label: 'Azure OpenAI', icon: '☁️' },
    { value: 'sentence_transformers', label: 'Local Models (Free)', icon: '💻' },
    { value: 'custom_gateway', label: 'Custom Gateway', icon: '🔧' },
    { value: 'google_gemini', label: 'Google Gemini', icon: '🔍' },
    { value: 'anthropic_claude', label: 'Anthropic Claude', icon: '🧠' }
  ];

  const modelOptions = {
    openai: [
      { value: 'text-embedding-ada-002', label: 'Ada-002 (Balanced)', cost: '$0.0001/1K' },
      { value: 'text-embedding-3-small', label: 'Embedding-3-Small (Fast)', cost: '$0.00002/1K' },
      { value: 'text-embedding-3-large', label: 'Embedding-3-Large (Quality)', cost: '$0.00013/1K' }
    ],
    sentence_transformers: [
      { value: 'all-MiniLM-L6-v2', label: 'MiniLM-L6-v2 (Fast)', cost: 'Free' },
      { value: 'all-mpnet-base-v2', label: 'MPNet-Base-v2 (Quality)', cost: 'Free' }
    ]
  };

  return (
    <div className="ai-provider-management">
      <Card title="AI Provider Configuration" extra={<SettingOutlined />}>
        <Tabs defaultActiveKey="providers">
          <Tabs.TabPane tab="Providers" key="providers">
            <ProviderConfigurationForm 
              providers={providers}
              providerOptions={providerOptions}
              modelOptions={modelOptions}
              onSave={handleSaveProvider}
            />
          </Tabs.TabPane>
          
          <Tabs.TabPane tab="Performance" key="performance">
            <PerformanceSettings />
          </Tabs.TabPane>
          
          <Tabs.TabPane tab="Cost Management" key="cost">
            <CostManagement />
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </div>
  );
};
```

#### **2. Model Selection Component (WrenAI-Inspired)**
```typescript
// services/frontend-app/src/components/ai/ModelSelection.tsx
import React from 'react';
import { Card, Select, Tag, Tooltip, Row, Col, Statistic } from 'antd';
import { ThunderboltOutlined, DollarOutlined, StarOutlined } from '@ant-design/icons';

interface ModelOption {
  value: string;
  label: string;
  provider: string;
  dimensions: number;
  cost_per_1k: number;
  performance_tier: 'fast' | 'balanced' | 'quality';
  capabilities: string[];
}

const ModelSelection: React.FC = () => {
  const modelOptions: ModelOption[] = [
    {
      value: 'text-embedding-ada-002',
      label: 'OpenAI Ada-002',
      provider: 'openai',
      dimensions: 1536,
      cost_per_1k: 0.0001,
      performance_tier: 'balanced',
      capabilities: ['embedding']
    },
    {
      value: 'all-MiniLM-L6-v2',
      label: 'MiniLM-L6-v2 (Local)',
      provider: 'sentence_transformers',
      dimensions: 384,
      cost_per_1k: 0,
      performance_tier: 'fast',
      capabilities: ['embedding']
    }
  ];

  const renderModelOption = (option: ModelOption) => (
    <Card 
      key={option.value}
      className="model-option-card"
      hoverable
      size="small"
    >
      <Row gutter={16}>
        <Col span={12}>
          <h4>{option.label}</h4>
          <Tag color={getProviderColor(option.provider)}>{option.provider}</Tag>
        </Col>
        <Col span={4}>
          <Statistic 
            title="Dimensions" 
            value={option.dimensions}
            prefix={<StarOutlined />}
          />
        </Col>
        <Col span={4}>
          <Statistic 
            title="Cost/1K" 
            value={option.cost_per_1k === 0 ? 'Free' : `$${option.cost_per_1k}`}
            prefix={<DollarOutlined />}
          />
        </Col>
        <Col span={4}>
          <Tag color={getPerformanceColor(option.performance_tier)}>
            <ThunderboltOutlined /> {option.performance_tier}
          </Tag>
        </Col>
      </Row>
    </Card>
  );

  return (
    <div className="model-selection">
      <h3>Select AI Models for Your Organization</h3>
      
      <div className="embedding-models">
        <h4>Embedding Models</h4>
        {modelOptions.map(renderModelOption)}
      </div>
      
      <div className="recommended-setup">
        <Card title="Recommended Setup" type="inner">
          <Alert
            message="High Performance + Cost Effective"
            description="Primary: Local MiniLM-L6-v2 (Free, 1000+ embeddings/sec) | Fallback: OpenAI Ada-002 (High quality)"
            type="success"
            showIcon
          />
        </Card>
      </div>
    </div>
  );
};
```

#### **3. Performance Monitoring Dashboard**
```typescript
// services/frontend-app/src/components/ai/AIPerformanceDashboard.tsx
import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Progress, Table, Tag } from 'antd';
import { Line, Pie } from '@ant-design/charts';
import { 
  ThunderboltOutlined, 
  DollarOutlined, 
  ClockCircleOutlined,
  CheckCircleOutlined 
} from '@ant-design/icons';

const AIPerformanceDashboard: React.FC = () => {
  const [performanceData, setPerformanceData] = useState({
    totalRequests: 0,
    avgResponseTime: 0,
    totalCost: 0,
    successRate: 0,
    providerUsage: [],
    responseTimeHistory: []
  });

  const performanceMetrics = [
    {
      title: 'Total AI Requests',
      value: performanceData.totalRequests,
      prefix: <ThunderboltOutlined />,
      suffix: 'requests'
    },
    {
      title: 'Avg Response Time',
      value: performanceData.avgResponseTime,
      prefix: <ClockCircleOutlined />,
      suffix: 'ms'
    },
    {
      title: 'Total Cost (30 days)',
      value: performanceData.totalCost,
      prefix: <DollarOutlined />,
      precision: 4
    },
    {
      title: 'Success Rate',
      value: performanceData.successRate,
      prefix: <CheckCircleOutlined />,
      suffix: '%'
    }
  ];

  const providerUsageColumns = [
    {
      title: 'Provider',
      dataIndex: 'provider',
      key: 'provider',
      render: (provider: string) => (
        <Tag color={getProviderColor(provider)}>{provider}</Tag>
      )
    },
    {
      title: 'Requests',
      dataIndex: 'requests',
      key: 'requests'
    },
    {
      title: 'Avg Response Time',
      dataIndex: 'avgResponseTime',
      key: 'avgResponseTime',
      render: (time: number) => `${time}ms`
    },
    {
      title: 'Cost',
      dataIndex: 'cost',
      key: 'cost',
      render: (cost: number) => `$${cost.toFixed(4)}`
    },
    {
      title: 'Success Rate',
      dataIndex: 'successRate',
      key: 'successRate',
      render: (rate: number) => (
        <Progress 
          percent={rate} 
          size="small" 
          status={rate > 95 ? 'success' : rate > 90 ? 'normal' : 'exception'}
        />
      )
    }
  ];

  return (
    <div className="ai-performance-dashboard">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        {performanceMetrics.map((metric, index) => (
          <Col span={6} key={index}>
            <Card>
              <Statistic {...metric} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col span={16}>
          <Card title="Response Time Trend">
            <Line
              data={performanceData.responseTimeHistory}
              xField="timestamp"
              yField="responseTime"
              smooth={true}
            />
          </Card>
        </Col>
        
        <Col span={8}>
          <Card title="Provider Usage Distribution">
            <Pie
              data={performanceData.providerUsage}
              angleField="requests"
              colorField="provider"
              radius={0.8}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Provider Performance Details" style={{ marginTop: 16 }}>
        <Table
          columns={providerUsageColumns}
          dataSource={performanceData.providerUsage}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
};
```

#### **4. Configuration Validation Component**
```typescript
// services/frontend-app/src/components/ai/ConfigurationValidation.tsx
import React, { useState } from 'react';
import { Card, Form, Button, Alert, Steps, Spin, Result } from 'antd';
import { CheckCircleOutlined, LoadingOutlined, ExclamationCircleOutlined } from '@ant-design/icons';

const ConfigurationValidation: React.FC = () => {
  const [validationState, setValidationState] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [validationResults, setValidationResults] = useState<any[]>([]);

  const validationSteps = [
    {
      title: 'Connection Test',
      description: 'Testing provider connectivity'
    },
    {
      title: 'Authentication',
      description: 'Validating API credentials'
    },
    {
      title: 'Model Access',
      description: 'Checking model availability'
    },
    {
      title: 'Performance Test',
      description: 'Running performance benchmark'
    }
  ];

  const runValidation = async () => {
    setValidationState('testing');
    
    try {
      // Test each provider configuration
      const results = await Promise.all([
        testProviderConnection(),
        testAuthentication(),
        testModelAccess(),
        testPerformance()
      ]);
      
      setValidationResults(results);
      setValidationState('success');
    } catch (error) {
      setValidationState('error');
    }
  };

  return (
    <Card title="AI Configuration Validation">
      <Steps
        current={getCurrentStep()}
        status={getStepStatus()}
        items={validationSteps}
      />
      
      <div style={{ marginTop: 24 }}>
        {validationState === 'idle' && (
          <Button type="primary" onClick={runValidation}>
            Test AI Configuration
          </Button>
        )}
        
        {validationState === 'testing' && (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <p>Testing AI configuration...</p>
          </div>
        )}
        
        {validationState === 'success' && (
          <Result
            status="success"
            title="AI Configuration Valid"
            subTitle="All providers are configured correctly and ready for use."
            extra={[
              <Button type="primary" key="save">Save Configuration</Button>,
              <Button key="test-again" onClick={runValidation}>Test Again</Button>
            ]}
          />
        )}
        
        {validationState === 'error' && (
          <Result
            status="error"
            title="Configuration Issues Found"
            subTitle="Please review and fix the issues below."
            extra={[
              <Button type="primary" key="retry" onClick={runValidation}>Retry Test</Button>
            ]}
          />
        )}
      </div>
      
      {validationResults.length > 0 && (
        <Card title="Validation Results" style={{ marginTop: 16 }}>
          {validationResults.map((result, index) => (
            <Alert
              key={index}
              message={result.message}
              description={result.description}
              type={result.success ? 'success' : 'error'}
              showIcon
              style={{ marginBottom: 8 }}
            />
          ))}
        </Card>
      )}
    </Card>
  );
};
```

## 📋 Implementation Tasks

### **Task 3-3.1: AI Configuration Menu Integration**
- [ ] Add AI Configuration to ETL service sidebar
- [ ] Create routing for AI configuration pages
- [ ] Implement navigation and breadcrumbs
- [ ] Add proper authentication checks

### **Task 3-3.2: Provider Management UI**
- [ ] Create AIProviderManagement component
- [ ] Implement provider selection interface
- [ ] Add model configuration forms
- [ ] Create provider status indicators

### **Task 3-3.3: Performance Dashboard**
- [ ] Implement AIPerformanceDashboard component
- [ ] Add real-time metrics display
- [ ] Create usage analytics charts
- [ ] Implement cost tracking visualization

### **Task 3-3.4: Configuration Validation**
- [ ] Create ConfigurationValidation component
- [ ] Implement provider testing logic
- [ ] Add validation result display
- [ ] Create error handling and recovery

### **Task 3-3.5: API Integration**
- [ ] Create AI configuration API endpoints
- [ ] Implement provider CRUD operations
- [ ] Add performance metrics API
- [ ] Create validation testing API

## ✅ Success Criteria

1. **User-Friendly Interface**: Intuitive AI configuration experience
2. **Multi-Provider Support**: Easy switching between AI providers
3. **Real-Time Monitoring**: Live performance and cost tracking
4. **Configuration Validation**: Automated testing of AI settings
5. **Professional UX**: Clean, enterprise-grade interface design
6. **Responsive Design**: Works on desktop and tablet devices

## 🔄 Completion Enables

- **Phase 3-4**: ETL AI integration with user-configured providers
- **Phase 3-5**: Vector generation with selected models
- **Phase 3-6**: AI agent foundation with configured providers
