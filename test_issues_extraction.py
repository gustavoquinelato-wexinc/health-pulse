#!/usr/bin/env python3
"""
Test script to manually run issues extraction
"""
import sys
import os
import asyncio

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

async def test_issues_extraction():
    """Test manually running issues extraction."""
    try:
        from app.etl.jira_extraction import _extract_issues_with_changelogs
        from app.etl.jira_client import JiraAPIClient
        from app.core.database import get_database
        from app.models.unified_models import Integration
        
        print("=== MANUAL ISSUES EXTRACTION TEST ===")
        
        # Get integration for tenant 1
        database = get_database()
        with database.get_read_session_context() as session:
            integration = session.query(Integration).filter(
                Integration.tenant_id == 1,
                Integration.active == True
            ).first()
            
            if not integration:
                print("❌ No active integration found for tenant 1")
                return
                
            print(f"✅ Found integration: {integration.name} (ID: {integration.id})")
        
        # Create Jira client
        jira_client = JiraAPIClient.create_from_integration(integration)
        if not jira_client:
            print("❌ Failed to create Jira client")
            return
            
        print("✅ Created Jira client")
        
        # Create a simple progress tracker
        class TestProgressTracker:
            def __init__(self):
                self.tenant_id = 1
                self.job_id = 1
                
            async def update_step_progress(self, step, progress, message):
                print(f"Progress {step}: {progress:.1%} - {message}")
                
            async def complete_step(self, step_index, message):
                print(f"Step {step_index} complete: {message}")
        
        progress_tracker = TestProgressTracker()
        
        print("🚀 Starting issues extraction...")
        
        # Run the extraction
        result = await _extract_issues_with_changelogs(
            jira_client=jira_client,
            integration_id=integration.id,
            tenant_id=1,
            incremental=True,
            progress_tracker=progress_tracker
        )
        
        print(f"✅ Extraction completed!")
        print(f"Result: {result}")
        
        # Check if raw data was created
        with database.get_read_session_context() as session:
            from sqlalchemy import text
            query = text("""
                SELECT id, type, status, created_at
                FROM raw_extraction_data
                WHERE tenant_id = 1 AND type = 'jira_issues_changelogs'
                ORDER BY created_at DESC
                LIMIT 5
            """)
            
            result_data = session.execute(query)
            records = result_data.fetchall()
            
            print(f"\n=== RAW DATA CHECK ===")
            if records:
                print("Recent jira_issues_changelogs records:")
                for record in records:
                    print(f"  ID {record[0]}: {record[1]} - {record[2]} - {record[3]}")
            else:
                print("❌ No jira_issues_changelogs records found")

    except Exception as e:
        print(f"❌ Error during issues extraction: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function to run the test."""
    asyncio.run(test_issues_extraction())

if __name__ == "__main__":
    main()
