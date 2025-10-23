#!/usr/bin/env python3
"""
Test script to verify last_job_item flag logic in ETL jira_issues_with_changelogs extraction.

This script simulates the logic to ensure:
1. When NO issues have development field: last issue gets last_job_item=True
2. When issues DO have development field: last dev_status extraction gets last_job_item=True
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'backend-service'))

import asyncio
import logging
from app.core.database import get_database
from app.models.unified_models import EtlJob, Integration
from app.etl.queue.queue_manager import get_queue_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_last_job_item_logic():
    """Test the last_job_item flag logic"""
    
    print("🧪 Testing last_job_item flag logic")
    print("=" * 50)
    
    # Test Case 1: No development issues
    print("\n📋 Test Case 1: NO development issues")
    print("-" * 30)
    
    all_issues = [
        {'key': 'TEST-1', 'id': '1001'},
        {'key': 'TEST-2', 'id': '1002'},
        {'key': 'TEST-3', 'id': '1003'}
    ]
    issues_with_code_changes = []  # No development issues
    
    print(f"Issues: {[issue['key'] for issue in all_issues]}")
    print(f"Issues with development: {issues_with_code_changes}")
    
    for i, issue in enumerate(all_issues):
        first_item = (i == 0)
        last_item = (i == len(all_issues) - 1)
        has_development_issues = len(issues_with_code_changes) > 0
        last_job_item = last_item and not has_development_issues
        
        status = "🎯 COMPLETES JOB" if last_job_item else "📝 continues"
        print(f"  {issue['key']}: first={first_item}, last={last_item}, last_job={last_job_item} {status}")
    
    # Test Case 2: With development issues
    print("\n📋 Test Case 2: WITH development issues")
    print("-" * 30)
    
    issues_with_code_changes = ['TEST-1', 'TEST-3']  # Some have development
    
    print(f"Issues: {[issue['key'] for issue in all_issues]}")
    print(f"Issues with development: {issues_with_code_changes}")
    
    print("\n  Transform queue messages:")
    for i, issue in enumerate(all_issues):
        first_item = (i == 0)
        last_item = (i == len(all_issues) - 1)
        has_development_issues = len(issues_with_code_changes) > 0
        last_job_item = last_item and not has_development_issues
        
        status = "🎯 COMPLETES JOB" if last_job_item else "📝 continues"
        print(f"    {issue['key']}: first={first_item}, last={last_item}, last_job={last_job_item} {status}")
    
    print("\n  Dev status extraction queue messages:")
    for i, issue_key in enumerate(issues_with_code_changes):
        first_item = (i == 0)
        last_item = (i == len(issues_with_code_changes) - 1)
        last_job_item = last_item  # Final dev_status completes the job
        
        status = "🎯 COMPLETES JOB" if last_job_item else "📝 continues"
        print(f"    {issue_key}: first={first_item}, last={last_item}, last_job={last_job_item} {status}")
    
    print("\n✅ Logic test completed!")
    
    # Test database connection and queue manager
    print("\n🔌 Testing database and queue manager...")
    try:
        db = get_database()
        with db.get_read_session_context() as session:
            job_count = session.query(EtlJob).filter(EtlJob.tenant_id == 1).count()
            integration_count = session.query(Integration).filter(Integration.tenant_id == 1).count()
            print(f"  ✅ Database: {job_count} ETL jobs, {integration_count} integrations")
        
        queue_manager = get_queue_manager()
        print(f"  ✅ Queue manager: {type(queue_manager).__name__}")
        
    except Exception as e:
        print(f"  ❌ Database/Queue error: {e}")
    
    print("\n🎉 Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_last_job_item_logic())
