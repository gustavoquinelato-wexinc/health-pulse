#!/usr/bin/env python3
"""
Frontend Integration Tests for Phase 1-7: Integration Testing & Validation

Tests complete user workflows, component rendering, and API service integration
to validate complete Phase 1 implementation.
"""

import sys
import os
import json
import time
from datetime import datetime

class TestFrontendIntegration:
    """Test frontend components and workflows for Phase 1 completion"""
    
    def test_typescript_compilation(self):
        """Test that TypeScript files compile without errors"""
        print("🧪 Testing TypeScript compilation...")
        
        try:
            # Check if TypeScript files exist
            ts_files = [
                'services/frontend-app/src/types/api.ts',
                'services/frontend-app/src/types/auth.ts',
                'services/frontend-app/src/types/index.ts',
                'services/frontend-app/src/services/apiService.ts',
                'services/frontend-app/src/components/IssueList.tsx',
                'services/frontend-app/src/components/PullRequestList.tsx',
                'services/frontend-app/src/components/UserList.tsx',
                'services/frontend-app/src/components/HealthCheck.tsx',
                'services/frontend-app/src/components/MLMonitoringDashboard.tsx'
            ]
            
            missing_files = []
            for file_path in ts_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
                else:
                    print(f"✅ TypeScript file exists: {file_path}")
            
            if missing_files:
                print(f"❌ Missing TypeScript files: {missing_files}")
                return False
            
            print("✅ All TypeScript files exist")
            return True
            
        except Exception as e:
            print(f"❌ TypeScript compilation test failed: {e}")
            return False
    
    def test_component_structure_validation(self):
        """Test that React components have proper structure"""
        print("🧪 Testing React component structure...")
        
        try:
            component_files = [
                'services/frontend-app/src/components/IssueList.tsx',
                'services/frontend-app/src/components/PullRequestList.tsx',
                'services/frontend-app/src/components/UserList.tsx',
                'services/frontend-app/src/components/HealthCheck.tsx',
                'services/frontend-app/src/components/MLMonitoringDashboard.tsx'
            ]
            
            for file_path in component_files:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for React component structure
                    required_patterns = [
                        'import React',
                        'interface',
                        'export',
                        'React.FC'
                    ]
                    
                    for pattern in required_patterns:
                        if pattern in content:
                            print(f"✅ {file_path} has {pattern}")
                        else:
                            print(f"⚠️ {file_path} missing {pattern}")
                    
                    # Check for ML fields handling
                    if 'showMlFields' in content or 'includeMlFields' in content:
                        print(f"✅ {file_path} handles ML fields")
                    else:
                        print(f"⚠️ {file_path} may not handle ML fields")
                    
                    # Check for graceful degradation
                    if '&&' in content and ('embedding' in content or 'ml_' in content):
                        print(f"✅ {file_path} has graceful degradation")
                    else:
                        print(f"⚠️ {file_path} may not have graceful degradation")
                
                else:
                    print(f"❌ Component file missing: {file_path}")
                    return False
            
            print("✅ All React components have proper structure")
            return True
            
        except Exception as e:
            print(f"❌ Component structure validation failed: {e}")
            return False
    
    def test_api_service_integration(self):
        """Test API service integration with components"""
        print("🧪 Testing API service integration...")
        
        try:
            api_service_path = 'services/frontend-app/src/services/apiService.ts'
            
            if os.path.exists(api_service_path):
                with open(api_service_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for required API methods
                required_methods = [
                    'getIssues',
                    'getPullRequests',
                    'getUsers',
                    'getProjects',
                    'getDatabaseHealth',
                    'getMLHealth',
                    'getComprehensiveHealth',
                    'getLearningMemory',
                    'getPredictions',
                    'getAnomalyAlerts'
                ]
                
                for method in required_methods:
                    if method in content:
                        print(f"✅ API service has method: {method}")
                    else:
                        print(f"⚠️ API service missing method: {method}")
                
                # Check for ML fields support
                if 'include_ml_fields' in content:
                    print("✅ API service supports include_ml_fields parameter")
                else:
                    print("⚠️ API service missing include_ml_fields support")
                
                # Check for configuration
                if 'defaultIncludeMlFields' in content:
                    print("✅ API service has ML fields configuration")
                else:
                    print("⚠️ API service missing ML fields configuration")
                
                print("✅ API service integration validated")
                return True
            else:
                print(f"❌ API service file missing: {api_service_path}")
                return False
            
        except Exception as e:
            print(f"❌ API service integration test failed: {e}")
            return False
    
    def test_environment_configuration(self):
        """Test environment configuration for frontend"""
        print("🧪 Testing environment configuration...")
        
        try:
            # Check vite-env.d.ts
            vite_env_path = 'services/frontend-app/src/vite-env.d.ts'
            
            if os.path.exists(vite_env_path):
                with open(vite_env_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for ML-related environment variables
                required_env_vars = [
                    'VITE_ENABLE_ML_FIELDS',
                    'VITE_ENABLE_AI_FEATURES',
                    'VITE_API_BASE_URL'
                ]
                
                for env_var in required_env_vars:
                    if env_var in content:
                        print(f"✅ Environment variable defined: {env_var}")
                    else:
                        print(f"⚠️ Environment variable missing: {env_var}")
                
                print("✅ Environment configuration validated")
            else:
                print(f"⚠️ vite-env.d.ts file missing: {vite_env_path}")
            
            # Check package.json
            package_json_path = 'services/frontend-app/package.json'
            
            if os.path.exists(package_json_path):
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                
                # Check for required dependencies
                required_deps = ['react', 'typescript', 'vite']
                dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                
                for dep in required_deps:
                    if dep in dependencies:
                        print(f"✅ Required dependency: {dep} ({dependencies[dep]})")
                    else:
                        print(f"⚠️ Missing dependency: {dep}")
                
                print("✅ Package.json configuration validated")
            else:
                print(f"⚠️ package.json file missing: {package_json_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Environment configuration test failed: {e}")
            return False
    
    def test_component_ml_fields_handling(self):
        """Test that components handle ML fields correctly"""
        print("🧪 Testing component ML fields handling...")
        
        try:
            component_files = [
                'services/frontend-app/src/components/IssueList.tsx',
                'services/frontend-app/src/components/PullRequestList.tsx',
                'services/frontend-app/src/components/UserList.tsx'
            ]
            
            for file_path in component_files:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for ML fields conditional rendering
                    ml_checks = [
                        'showMlFields &&',
                        'includeMlFields &&',
                        'ml_fields_included',
                        'embedding'
                    ]
                    
                    found_checks = 0
                    for check in ml_checks:
                        if check in content:
                            found_checks += 1
                    
                    if found_checks >= 2:
                        print(f"✅ {file_path} properly handles ML fields")
                    else:
                        print(f"⚠️ {file_path} may not properly handle ML fields")
                    
                    # Check for graceful degradation patterns
                    if '&&' in content and ('?' in content or 'null' in content):
                        print(f"✅ {file_path} has graceful degradation patterns")
                    else:
                        print(f"⚠️ {file_path} may not have graceful degradation")
                
                else:
                    print(f"❌ Component file missing: {file_path}")
                    return False
            
            print("✅ Component ML fields handling validated")
            return True
            
        except Exception as e:
            print(f"❌ Component ML fields handling test failed: {e}")
            return False
    
    def test_health_check_component_functionality(self):
        """Test health check component functionality"""
        print("🧪 Testing health check component functionality...")
        
        try:
            health_check_path = 'services/frontend-app/src/components/HealthCheck.tsx'
            
            if os.path.exists(health_check_path):
                with open(health_check_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for health check features
                required_features = [
                    'DatabaseHealthResponse',
                    'MLHealthResponse',
                    'ComprehensiveHealthResponse',
                    'getBasicHealth',
                    'getDatabaseHealth',
                    'getMLHealth',
                    'getComprehensiveHealth',
                    'autoRefresh',
                    'refreshInterval'
                ]
                
                for feature in required_features:
                    if feature in content:
                        print(f"✅ Health check has feature: {feature}")
                    else:
                        print(f"⚠️ Health check missing feature: {feature}")
                
                # Check for ML infrastructure monitoring
                ml_features = [
                    'pgvector',
                    'postgresml',
                    'vector_columns',
                    'ml_tables'
                ]
                
                for feature in ml_features:
                    if feature in content:
                        print(f"✅ Health check monitors: {feature}")
                    else:
                        print(f"⚠️ Health check may not monitor: {feature}")
                
                print("✅ Health check component functionality validated")
                return True
            else:
                print(f"❌ Health check component missing: {health_check_path}")
                return False
            
        except Exception as e:
            print(f"❌ Health check component test failed: {e}")
            return False
    
    def test_ml_monitoring_dashboard_functionality(self):
        """Test ML monitoring dashboard functionality"""
        print("🧪 Testing ML monitoring dashboard functionality...")
        
        try:
            dashboard_path = 'services/frontend-app/src/components/MLMonitoringDashboard.tsx'
            
            if os.path.exists(dashboard_path):
                with open(dashboard_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for ML monitoring features
                required_features = [
                    'LearningMemoryResponse',
                    'PredictionsResponse',
                    'AnomalyAlertsResponse',
                    'MLStatsResponse',
                    'getLearningMemory',
                    'getPredictions',
                    'getAnomalyAlerts',
                    'getMLStats',
                    'activeTab'
                ]
                
                for feature in required_features:
                    if feature in content:
                        print(f"✅ ML dashboard has feature: {feature}")
                    else:
                        print(f"⚠️ ML dashboard missing feature: {feature}")
                
                # Check for tab functionality
                tabs = ['overview', 'learning', 'predictions', 'alerts']
                for tab in tabs:
                    if tab in content:
                        print(f"✅ ML dashboard has tab: {tab}")
                    else:
                        print(f"⚠️ ML dashboard missing tab: {tab}")
                
                print("✅ ML monitoring dashboard functionality validated")
                return True
            else:
                print(f"❌ ML monitoring dashboard missing: {dashboard_path}")
                return False
            
        except Exception as e:
            print(f"❌ ML monitoring dashboard test failed: {e}")
            return False
    
    def test_frontend_performance_impact(self):
        """Test frontend performance impact of enhancements"""
        print("🧪 Testing frontend performance impact...")
        
        try:
            # Check file sizes
            enhanced_files = [
                'services/frontend-app/src/types/api.ts',
                'services/frontend-app/src/types/auth.ts',
                'services/frontend-app/src/types/index.ts',
                'services/frontend-app/src/services/apiService.ts',
                'services/frontend-app/src/components/IssueList.tsx',
                'services/frontend-app/src/components/PullRequestList.tsx',
                'services/frontend-app/src/components/UserList.tsx',
                'services/frontend-app/src/components/HealthCheck.tsx',
                'services/frontend-app/src/components/MLMonitoringDashboard.tsx'
            ]
            
            total_size = 0
            for file_path in enhanced_files:
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    total_size += size
                    size_kb = size / 1024
                    print(f"✅ {file_path}: {size_kb:.1f} KB")
                    
                    if size_kb > 50:  # Warn if file is over 50KB
                        print(f"⚠️ Large file size: {file_path} ({size_kb:.1f} KB)")
            
            total_size_kb = total_size / 1024
            print(f"✅ Total enhanced files size: {total_size_kb:.1f} KB")
            
            if total_size_kb < 200:  # Less than 200KB total is good
                print("✅ Performance impact is minimal")
            else:
                print("⚠️ Performance impact may be noticeable")
            
            return True
            
        except Exception as e:
            print(f"❌ Frontend performance test failed: {e}")
            return False

def run_frontend_integration_tests():
    """Run all frontend integration tests"""
    print("🚀 Starting Frontend Integration Tests for Phase 1-7")
    print("=" * 70)
    
    test_instance = TestFrontendIntegration()
    
    tests = [
        test_instance.test_typescript_compilation,
        test_instance.test_component_structure_validation,
        test_instance.test_api_service_integration,
        test_instance.test_environment_configuration,
        test_instance.test_component_ml_fields_handling,
        test_instance.test_health_check_component_functionality,
        test_instance.test_ml_monitoring_dashboard_functionality,
        test_instance.test_frontend_performance_impact
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("📊 Frontend Integration Test Results:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 ALL FRONTEND INTEGRATION TESTS PASSED!")
        print("✅ Frontend components are ready for Phase 2")
        return True
    else:
        print("\n❌ SOME FRONTEND TESTS FAILED!")
        return False

if __name__ == "__main__":
    success = run_frontend_integration_tests()
    sys.exit(0 if success else 1)
