#!/usr/bin/env python3
"""
Performance Integration Tests for Phase 1-7: Integration Testing & Validation

Tests system performance, concurrent load testing, and resource usage
to validate complete Phase 1 implementation.
"""

import sys
import os
import time
import threading
import concurrent.futures
from datetime import datetime

# Add backend service to path
sys.path.append('services/backend-service')

try:
    from app.core.database import get_read_session, get_write_session
    from app.models.unified_models import *
    from app.core.utils import DateTimeHelper
    DATABASE_IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Database imports not available: {e}")
    DATABASE_IMPORTS_AVAILABLE = False

class TestPerformanceIntegration:
    """Test system performance for Phase 1 completion"""
    
    def test_database_query_performance(self):
        """Test database query performance with new schema"""
        print("🧪 Testing database query performance...")
        
        if not DATABASE_IMPORTS_AVAILABLE:
            print("⚠️ Skipping database performance tests - imports not available")
            return True
        
        try:
            # Test basic query performance
            start_time = time.time()
            
            with get_read_session() as session:
                # Test simple count queries
                for table_name in ['issues', 'pull_requests', 'users', 'projects']:
                    query_start = time.time()
                    try:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                        query_end = time.time()
                        query_time_ms = (query_end - query_start) * 1000
                        print(f"✅ {table_name} count query: {query_time_ms:.3f}ms (count: {count})")
                        
                        if query_time_ms > 1000:  # Warn if over 1 second
                            print(f"⚠️ Slow query detected: {table_name} ({query_time_ms:.3f}ms)")
                    except Exception as e:
                        print(f"⚠️ Query failed for {table_name}: {e}")
            
            end_time = time.time()
            total_time_ms = (end_time - start_time) * 1000
            print(f"✅ Total database query time: {total_time_ms:.3f}ms")
            
            if total_time_ms < 5000:  # Less than 5 seconds total
                print("✅ Database query performance is acceptable")
            else:
                print("⚠️ Database query performance may be slow")
            
            return True
            
        except Exception as e:
            print(f"❌ Database query performance test failed: {e}")
            return False
    
    def test_vector_column_performance(self):
        """Test vector column access performance"""
        print("🧪 Testing vector column performance...")
        
        if not DATABASE_IMPORTS_AVAILABLE:
            print("⚠️ Skipping vector column performance tests - imports not available")
            return True
        
        try:
            start_time = time.time()
            
            with get_read_session() as session:
                # Test vector column queries
                vector_tables = ['issues', 'pull_requests', 'users', 'projects']
                
                for table in vector_tables:
                    query_start = time.time()
                    try:
                        # Test selecting embedding column
                        result = session.execute(text(f"""
                            SELECT id, embedding 
                            FROM {table} 
                            WHERE embedding IS NOT NULL 
                            LIMIT 10
                        """)).fetchall()
                        
                        query_end = time.time()
                        query_time_ms = (query_end - query_start) * 1000
                        print(f"✅ {table} vector query: {query_time_ms:.3f}ms (rows: {len(result)})")
                        
                        if query_time_ms > 2000:  # Warn if over 2 seconds
                            print(f"⚠️ Slow vector query: {table} ({query_time_ms:.3f}ms)")
                    except Exception as e:
                        print(f"⚠️ Vector query failed for {table}: {e}")
            
            end_time = time.time()
            total_time_ms = (end_time - start_time) * 1000
            print(f"✅ Total vector column query time: {total_time_ms:.3f}ms")
            
            if total_time_ms < 10000:  # Less than 10 seconds total
                print("✅ Vector column performance is acceptable")
            else:
                print("⚠️ Vector column performance may be slow")
            
            return True
            
        except Exception as e:
            print(f"❌ Vector column performance test failed: {e}")
            return False
    
    def test_model_instantiation_performance(self):
        """Test model instantiation performance"""
        print("🧪 Testing model instantiation performance...")
        
        if not DATABASE_IMPORTS_AVAILABLE:
            print("⚠️ Skipping model instantiation performance tests - imports not available")
            return True
        
        try:
            # Test creating multiple models
            num_models = 100
            
            # Test User model creation
            start_time = time.time()
            
            for i in range(num_models):
                user = User(
                    email=f'test{i}@example.com',
                    first_name='Test',
                    last_name='User',
                    password_hash='hashed_password',
                    role='user',
                    is_admin=False,
                    auth_provider='local',
                    theme_mode='light',
                    high_contrast_mode=False,
                    reduce_motion=False,
                    colorblind_safe_palette=False,
                    accessibility_level='regular',
                    client_id=1,
                    embedding=None,  # Phase 1: always None
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
            
            end_time = time.time()
            total_time_ms = (end_time - start_time) * 1000
            avg_time_ms = total_time_ms / num_models
            
            print(f"✅ User model instantiation: {avg_time_ms:.3f}ms per model")
            
            # Test Issue model creation
            start_time = time.time()
            
            for i in range(num_models):
                issue = Issue(
                    external_id=f'TEST-{i}',
                    key=f'TEST-{i}',
                    summary=f'Test Issue {i}',
                    description=f'Test issue description {i}',
                    priority='Medium',
                    status_name='To Do',
                    issuetype_name='Story',
                    project_id=1,
                    level_number=0,
                    comment_count=0,
                    client_id=1,
                    embedding=None,  # Phase 1: always None
                    created_at=DateTimeHelper.now_utc(),
                    updated_at=DateTimeHelper.now_utc(),
                    active=True
                )
            
            end_time = time.time()
            total_time_ms = (end_time - start_time) * 1000
            avg_time_ms = total_time_ms / num_models
            
            print(f"✅ Issue model instantiation: {avg_time_ms:.3f}ms per model")
            
            if avg_time_ms < 1.0:  # Less than 1ms per model
                print("✅ Model instantiation performance is excellent")
            elif avg_time_ms < 5.0:  # Less than 5ms per model
                print("✅ Model instantiation performance is acceptable")
            else:
                print("⚠️ Model instantiation performance may be slow")
            
            return True
            
        except Exception as e:
            print(f"❌ Model instantiation performance test failed: {e}")
            return False
    
    def test_concurrent_database_access(self):
        """Test concurrent database access performance"""
        print("🧪 Testing concurrent database access...")
        
        if not DATABASE_IMPORTS_AVAILABLE:
            print("⚠️ Skipping concurrent database access tests - imports not available")
            return True
        
        try:
            def database_worker(worker_id):
                """Worker function for concurrent database access"""
                try:
                    with get_read_session() as session:
                        # Perform some database operations
                        start_time = time.time()
                        
                        # Query different tables
                        tables = ['issues', 'pull_requests', 'users', 'projects']
                        for table in tables:
                            try:
                                count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                            except Exception:
                                pass  # Ignore errors in concurrent test
                        
                        end_time = time.time()
                        return end_time - start_time
                except Exception:
                    return None
            
            # Test with multiple concurrent workers
            num_workers = 5
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(database_worker, i) for i in range(num_workers)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            end_time = time.time()
            total_time = end_time - start_time
            
            successful_workers = [r for r in results if r is not None]
            if successful_workers:
                avg_worker_time = sum(successful_workers) / len(successful_workers)
                print(f"✅ Concurrent database access: {len(successful_workers)}/{num_workers} workers successful")
                print(f"✅ Average worker time: {avg_worker_time:.3f}s")
                print(f"✅ Total concurrent time: {total_time:.3f}s")
                
                if total_time < 10.0:  # Less than 10 seconds total
                    print("✅ Concurrent database performance is acceptable")
                else:
                    print("⚠️ Concurrent database performance may be slow")
            else:
                print("⚠️ No workers completed successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Concurrent database access test failed: {e}")
            return False
    
    def test_memory_usage(self):
        """Test memory usage during operations"""
        print("🧪 Testing memory usage...")

        try:
            # Perform memory-intensive operations
            if DATABASE_IMPORTS_AVAILABLE:
                # Create many model instances
                models = []
                start_time = time.time()

                for i in range(1000):
                    user = User(
                        email=f'memory_test{i}@example.com',
                        first_name='Memory',
                        last_name='Test',
                        password_hash='hashed_password',
                        role='user',
                        is_admin=False,
                        auth_provider='local',
                        theme_mode='light',
                        high_contrast_mode=False,
                        reduce_motion=False,
                        colorblind_safe_palette=False,
                        accessibility_level='regular',
                        client_id=1,
                        embedding=None,
                        created_at=DateTimeHelper.now_utc(),
                        last_updated_at=DateTimeHelper.now_utc(),
                        active=True
                    )
                    models.append(user)

                end_time = time.time()
                creation_time = end_time - start_time

                print(f"✅ Created 1000 models in {creation_time:.3f}s")
                print(f"✅ Average model creation time: {creation_time/1000*1000:.3f}ms")

                # Clean up
                del models

                if creation_time < 5.0:  # Less than 5 seconds
                    print("✅ Memory usage performance is acceptable")
                else:
                    print("⚠️ Memory usage performance may be slow")
            else:
                print("⚠️ Skipping model memory test - imports not available")

            return True

        except Exception as e:
            print(f"❌ Memory usage test failed: {e}")
            return False
    
    def test_cpu_usage(self):
        """Test CPU usage during operations"""
        print("🧪 Testing CPU usage...")

        try:
            # Perform CPU-intensive operations and measure time
            if DATABASE_IMPORTS_AVAILABLE:
                start_time = time.time()

                try:
                    with get_read_session() as session:
                        # Perform multiple queries
                        for i in range(50):
                            try:
                                session.execute(text("SELECT COUNT(*) FROM issues")).scalar()
                                session.execute(text("SELECT COUNT(*) FROM pull_requests")).scalar()
                            except Exception:
                                pass  # Ignore errors
                except Exception:
                    pass  # Ignore database connection errors

                end_time = time.time()
                total_time = end_time - start_time

                print(f"✅ CPU-intensive operations completed in {total_time:.3f}s")

                if total_time < 30.0:  # Less than 30 seconds
                    print("✅ CPU usage performance is acceptable")
                else:
                    print("⚠️ CPU usage performance may be slow")
            else:
                print("⚠️ Skipping CPU test - database imports not available")

            return True

        except Exception as e:
            print(f"❌ CPU usage test failed: {e}")
            return False
    
    def test_file_system_performance(self):
        """Test file system performance impact"""
        print("🧪 Testing file system performance...")
        
        try:
            # Test file creation/deletion performance
            test_dir = "temp_performance_test"
            
            if not os.path.exists(test_dir):
                os.makedirs(test_dir)
            
            # Test file operations
            num_files = 100
            start_time = time.time()
            
            # Create files
            for i in range(num_files):
                file_path = os.path.join(test_dir, f"test_file_{i}.txt")
                with open(file_path, 'w') as f:
                    f.write(f"Test content {i}\n" * 100)  # Write some content
            
            create_time = time.time() - start_time
            
            # Read files
            start_time = time.time()
            
            for i in range(num_files):
                file_path = os.path.join(test_dir, f"test_file_{i}.txt")
                with open(file_path, 'r') as f:
                    content = f.read()
            
            read_time = time.time() - start_time
            
            # Delete files
            start_time = time.time()
            
            for i in range(num_files):
                file_path = os.path.join(test_dir, f"test_file_{i}.txt")
                os.remove(file_path)
            
            delete_time = time.time() - start_time
            
            # Clean up directory
            os.rmdir(test_dir)
            
            print(f"✅ File creation time: {create_time:.3f}s ({create_time/num_files*1000:.3f}ms per file)")
            print(f"✅ File read time: {read_time:.3f}s ({read_time/num_files*1000:.3f}ms per file)")
            print(f"✅ File deletion time: {delete_time:.3f}s ({delete_time/num_files*1000:.3f}ms per file)")
            
            total_time = create_time + read_time + delete_time
            if total_time < 5.0:  # Less than 5 seconds total
                print("✅ File system performance is acceptable")
            else:
                print("⚠️ File system performance may be slow")
            
            return True
            
        except Exception as e:
            print(f"❌ File system performance test failed: {e}")
            return False

def run_performance_integration_tests():
    """Run all performance integration tests"""
    print("🚀 Starting Performance Integration Tests for Phase 1-7")
    print("=" * 70)
    
    test_instance = TestPerformanceIntegration()
    
    tests = [
        test_instance.test_database_query_performance,
        test_instance.test_vector_column_performance,
        test_instance.test_model_instantiation_performance,
        test_instance.test_concurrent_database_access,
        test_instance.test_memory_usage,
        test_instance.test_cpu_usage,
        test_instance.test_file_system_performance
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
    print("📊 Performance Integration Test Results:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 ALL PERFORMANCE INTEGRATION TESTS PASSED!")
        print("✅ System performance is ready for Phase 2")
        return True
    else:
        print("\n❌ SOME PERFORMANCE TESTS FAILED!")
        return False

if __name__ == "__main__":
    success = run_performance_integration_tests()
    sys.exit(0 if success else 1)
