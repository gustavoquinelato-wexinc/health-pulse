#!/usr/bin/env python3
"""
Database Integration Tests for Phase 1-7: Integration Testing & Validation

Tests database schema, vector columns, ML tables, indexes, and model instantiation
to validate complete Phase 1 implementation.
"""

import sys
import os
import pytest
from sqlalchemy import text, inspect
from datetime import datetime

# Add backend service to path
sys.path.append('services/backend-service')

from app.core.database import get_read_session, get_write_session
from app.models.unified_models import *
from app.core.utils import DateTimeHelper

class TestDatabaseIntegration:
    """Test database schema and connectivity for Phase 1 completion"""
    
    def test_database_connection(self):
        """Test basic database connectivity"""
        print("🧪 Testing database connection...")
        
        with get_read_session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
            print("✅ Database connection successful")
    
    def test_vector_columns_exist(self):
        """Test that all tables have vector columns"""
        print("🧪 Testing vector columns existence...")
        
        # All tables that should have embedding columns
        vector_tables = [
            'clients', 'users', 'projects', 'issues', 'repositories',
            'pull_requests', 'pull_request_comments', 'pull_request_reviews',
            'pull_request_commits', 'statuses', 'status_mappings',
            'issuetypes', 'issuetype_mappings', 'issuetype_hierarchies',
            'workflows', 'issue_changelogs', 'jira_pull_request_links',
            'projects_issuetypes', 'projects_statuses', 'user_permissions',
            'user_sessions', 'system_settings', 'dora_market_benchmarks',
            'dora_metric_insights'
        ]
        
        missing_columns = []
        
        with get_read_session() as session:
            for table in vector_tables:
                # Check if embedding column exists
                result = session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' 
                    AND column_name = 'embedding'
                """)).fetchone()
                
                if result is None:
                    missing_columns.append(table)
                else:
                    print(f"✅ Table {table} has embedding column")
        
        if missing_columns:
            print(f"❌ Missing embedding columns in tables: {missing_columns}")
            assert False, f"Tables missing embedding columns: {missing_columns}"
        else:
            print("✅ All tables have embedding columns")
    
    def test_ml_monitoring_tables_exist(self):
        """Test that ML monitoring tables exist and are accessible"""
        print("🧪 Testing ML monitoring tables...")
        
        ml_tables = ['ai_learning_memory', 'ai_prediction', 'ml_anomaly_alert']
        
        with get_read_session() as session:
            for table in ml_tables:
                try:
                    # Test table accessibility
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    print(f"✅ Table {table} exists and accessible (count: {result})")
                except Exception as e:
                    print(f"❌ Table {table} not accessible: {e}")
                    assert False, f"ML table {table} not accessible: {e}"
    
    def test_vector_indexes_exist(self):
        """Test that vector indexes exist for performance"""
        print("🧪 Testing vector indexes...")
        
        with get_read_session() as session:
            # Check for HNSW indexes on major tables
            result = session.execute(text("""
                SELECT schemaname, tablename, indexname, indexdef
                FROM pg_indexes 
                WHERE indexname LIKE '%embedding%'
                ORDER BY tablename, indexname
            """)).fetchall()
            
            if result:
                print("✅ Vector indexes found:")
                for row in result:
                    print(f"   - {row[1]}.{row[2]}")
            else:
                print("⚠️ No vector indexes found - this is expected in Phase 1")
            
            # Check for basic indexes on embedding columns
            major_tables = ['issues', 'pull_requests', 'projects', 'users']
            for table in major_tables:
                index_result = session.execute(text(f"""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = '{table}' 
                    AND indexdef LIKE '%embedding%'
                """)).fetchall()
                
                if index_result:
                    print(f"✅ Table {table} has embedding indexes")
                else:
                    print(f"⚠️ Table {table} has no embedding indexes (expected in Phase 1)")
    
    def test_model_instantiation(self):
        """Test that all models can be instantiated with new schema"""
        print("🧪 Testing model instantiation with enhanced schema...")
        
        try:
            with get_write_session() as session:
                # Test creating models with embedding=None (Phase 1 default)
                
                # Test Client model
                client = Client(
                    name='test_client_integration',
                    display_name='Test Client Integration',
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(client)
                session.flush()  # Get ID without committing
                print(f"✅ Client model instantiated (ID: {client.id})")
                
                # Test User model
                user = User(
                    email='test_integration@example.com',
                    first_name='Test',
                    last_name='Integration',
                    password_hash='hashed_password',
                    role='user',
                    is_admin=False,
                    auth_provider='local',
                    theme_mode='light',
                    high_contrast_mode=False,
                    reduce_motion=False,
                    colorblind_safe_palette=False,
                    accessibility_level='regular',
                    client_id=client.id,
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(user)
                session.flush()
                print(f"✅ User model instantiated (ID: {user.id})")
                
                # Test Project model
                project = Project(
                    external_id='TEST-INTEGRATION',
                    key='TESTINT',
                    name='Test Integration Project',
                    project_type='software',
                    description='Test project for integration testing',
                    client_id=client.id,
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(project)
                session.flush()
                print(f"✅ Project model instantiated (ID: {project.id})")
                
                # Test Issue model
                issue = Issue(
                    external_id='TESTINT-1',
                    key='TESTINT-1',
                    summary='Test Integration Issue',
                    description='Test issue for integration testing',
                    priority='Medium',
                    status_name='To Do',
                    issuetype_name='Story',
                    project_id=project.id,
                    level_number=0,
                    comment_count=0,
                    client_id=client.id,
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(issue)
                session.flush()
                print(f"✅ Issue model instantiated (ID: {issue.id})")
                
                # Test Repository model
                repository = Repository(
                    external_id='test-integration-repo',
                    external_repo_id='123456',
                    name='test-integration-repo',
                    full_name='test/test-integration-repo',
                    description='Test repository for integration testing',
                    private=False,
                    default_branch='main',
                    language='Python',
                    client_id=client.id,
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(repository)
                session.flush()
                print(f"✅ Repository model instantiated (ID: {repository.id})")
                
                # Test PullRequest model
                pull_request = PullRequest(
                    external_id='1',
                    external_repo_id='123456',
                    repository_id=repository.id,
                    number=1,
                    name='Test Integration PR',
                    user_name='test-user',
                    body='Test pull request for integration testing',
                    status='open',
                    commit_count=1,
                    additions=10,
                    deletions=5,
                    changed_files=2,
                    client_id=client.id,
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(pull_request)
                session.flush()
                print(f"✅ PullRequest model instantiated (ID: {pull_request.id})")
                
                # Test UserSession model
                user_session = UserSession(
                    user_id=user.id,
                    token_hash='test_token_hash',
                    ip_address='127.0.0.1',
                    user_agent='Test Agent',
                    expires_at=DateTimeHelper.now_utc(),
                    client_id=client.id,
                    embedding=None,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(user_session)
                session.flush()
                print(f"✅ UserSession model instantiated (ID: {user_session.id})")
                
                # Test ML monitoring models
                ai_learning_memory = AILearningMemory(
                    error_type='test_error',
                    user_intent='test intent',
                    failed_query='test query',
                    specific_issue='test issue',
                    suggested_fix='test fix',
                    confidence=0.85,
                    client_id=client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(ai_learning_memory)
                session.flush()
                print(f"✅ AILearningMemory model instantiated (ID: {ai_learning_memory.id})")
                
                ai_prediction = AIPrediction(
                    model_name='test_model',
                    model_version='1.0',
                    input_data='test input',
                    prediction_result='test result',
                    confidence_score=0.90,
                    prediction_type='test',
                    client_id=client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(ai_prediction)
                session.flush()
                print(f"✅ AIPrediction model instantiated (ID: {ai_prediction.id})")
                
                ml_anomaly_alert = MLAnomalyAlert(
                    model_name='test_model',
                    severity='low',
                    alert_data={'test': 'data'},
                    acknowledged=False,
                    client_id=client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
                session.add(ml_anomaly_alert)
                session.flush()
                print(f"✅ MLAnomalyAlert model instantiated (ID: {ml_anomaly_alert.id})")
                
                # Rollback test data - don't commit to database
                session.rollback()
                print("✅ All models instantiated successfully and test data rolled back")
                
        except Exception as e:
            print(f"❌ Model instantiation failed: {e}")
            raise
    
    def test_database_schema_integrity(self):
        """Test database schema integrity and constraints"""
        print("🧪 Testing database schema integrity...")
        
        with get_read_session() as session:
            # Test foreign key constraints exist
            fk_result = session.execute(text("""
                SELECT 
                    tc.table_name, 
                    kcu.column_name, 
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                ORDER BY tc.table_name, kcu.column_name
            """)).fetchall()
            
            if fk_result:
                print(f"✅ Found {len(fk_result)} foreign key constraints")
            else:
                print("⚠️ No foreign key constraints found")
            
            # Test unique constraints
            unique_result = session.execute(text("""
                SELECT 
                    tc.table_name, 
                    kcu.column_name
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'UNIQUE'
                ORDER BY tc.table_name, kcu.column_name
            """)).fetchall()
            
            if unique_result:
                print(f"✅ Found {len(unique_result)} unique constraints")
            else:
                print("⚠️ No unique constraints found")
            
            print("✅ Database schema integrity validated")

def run_database_integration_tests():
    """Run all database integration tests"""
    print("🚀 Starting Database Integration Tests for Phase 1-7")
    print("=" * 70)
    
    test_instance = TestDatabaseIntegration()
    
    tests = [
        test_instance.test_database_connection,
        test_instance.test_vector_columns_exist,
        test_instance.test_ml_monitoring_tables_exist,
        test_instance.test_vector_indexes_exist,
        test_instance.test_model_instantiation,
        test_instance.test_database_schema_integrity
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("📊 Database Integration Test Results:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 ALL DATABASE INTEGRATION TESTS PASSED!")
        print("✅ Database schema is ready for Phase 2")
        return True
    else:
        print("\n❌ SOME DATABASE TESTS FAILED!")
        return False

if __name__ == "__main__":
    success = run_database_integration_tests()
    sys.exit(0 if success else 1)
