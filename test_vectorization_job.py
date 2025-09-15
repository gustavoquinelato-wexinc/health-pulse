#!/usr/bin/env python3
"""
Test script for the new Vectorization Job.

This script tests the dedicated vectorization job that processes the queue
independently from ETL jobs.
"""

import asyncio
import sys
import os

# Add the ETL service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'etl-service'))

async def test_vectorization_job():
    """Test the vectorization job functionality."""
    
    print("🧪 Testing Vectorization Job...")
    
    try:
        # Import ETL modules
        from app.core.database import get_database
        from app.models.unified_models import JobSchedule
        from app.jobs.vectorization.vectorization_job import VectorizationJobProcessor
        
        print("✅ Imports successful")
        
        # Get database connection
        database = get_database()
        
        # Test with tenant 1
        tenant_id = 1
        
        with database.get_session() as session:
            # Find the vectorization job for tenant 1
            vectorization_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'Vectorization',
                JobSchedule.tenant_id == tenant_id
            ).first()
            
            if not vectorization_job:
                print(f"❌ Vectorization job not found for tenant {tenant_id}")
                print("   Make sure to run database migrations first")
                return False
            
            print(f"✅ Found vectorization job: ID {vectorization_job.id}, Status: {vectorization_job.status}")
            
            # Test the processor
            processor = VectorizationJobProcessor()
            
            # Get queue statistics
            queue_stats = await processor._get_queue_statistics(session, tenant_id)
            print(f"📊 Queue statistics: {queue_stats}")
            
            if queue_stats['pending'] == 0:
                print("ℹ️  No pending items in queue - this is expected if no ETL jobs have run recently")
            else:
                print(f"🔄 Found {queue_stats['pending']} pending items ready for processing")
            
            # Test the job execution (dry run)
            print("🚀 Testing vectorization job execution...")
            result = await processor.process_vectorization_queue(session, vectorization_job)
            
            print(f"📋 Job execution result:")
            print(f"   Status: {result.get('status')}")
            print(f"   Message: {result.get('message')}")
            print(f"   Items processed: {result.get('items_processed', 0)}")
            print(f"   Items failed: {result.get('items_failed', 0)}")
            
            return result.get('status') == 'success'
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

async def test_orchestrator_integration():
    """Test that the orchestrator can trigger the vectorization job."""
    
    print("\n🔧 Testing Orchestrator Integration...")
    
    try:
        from app.jobs.orchestrator import trigger_vectorization_sync
        
        # Test triggering the vectorization job
        result = await trigger_vectorization_sync(
            force_manual=True,
            tenant_id=1
        )
        
        print(f"📋 Trigger result:")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        print(f"   Job name: {result.get('job_name')}")
        
        return result.get('status') == 'triggered'
        
    except Exception as e:
        print(f"❌ Orchestrator test failed: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main test function."""
    
    print("🎯 Testing New Vectorization Job Architecture")
    print("=" * 50)
    
    # Test 1: Basic job functionality
    job_test_passed = await test_vectorization_job()
    
    # Test 2: Orchestrator integration
    orchestrator_test_passed = await test_orchestrator_integration()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Vectorization Job: {'✅ PASSED' if job_test_passed else '❌ FAILED'}")
    print(f"   Orchestrator Integration: {'✅ PASSED' if orchestrator_test_passed else '❌ FAILED'}")
    
    if job_test_passed and orchestrator_test_passed:
        print("\n🎉 All tests passed! The vectorization job is ready to use.")
        print("\n📋 Next steps:")
        print("   1. The vectorization job will now run as part of the job sequence")
        print("   2. ETL jobs (Jira/GitHub) will only queue data, not trigger processing")
        print("   3. The dedicated vectorization job will process the queue")
        print("   4. You can manually trigger it via the orchestrator UI")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
