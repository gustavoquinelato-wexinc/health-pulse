#!/usr/bin/env python3
"""
Test script to simulate ETL AI vectorization with real database data
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the ETL service to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.models.unified_models import Project, Wit, Status, Changelog
from app.core.database import get_database
from app.clients.ai_client import bulk_store_entity_vectors_for_etl
from app.jobs.orchestrator import _get_job_auth_token

async def test_projects_vectorization():
    """Test vectorization with real project data from database"""
    print("🧪 Testing Projects AI Vectorization...")
    print("=" * 60)
    
    database = get_database()
    with database.get_read_session_context() as session:
        
        # Get first 3 projects from database
        projects = session.query(Project).filter(Project.tenant_id == 1).limit(3).all()
        
        if not projects:
            print("❌ No projects found in database")
            return
            
        print(f"Found {len(projects)} projects to test:")
        for project in projects:
            print(f"   • {project.key}: {project.name} (ID: {project.external_id})")
        
        # Prepare entities like ETL does
        entities_to_create = []
        for project in projects:
            try:
                # Create entity data for AI processing
                entity_data = {
                    "external_id": project.external_id,
                    "key": project.key,
                    "name": project.name,
                    "project_type": project.project_type
                }
                
                # Remove None values to create cleaner text content
                entity_data = {k: v for k, v in entity_data.items() if v is not None}
                
                entities_to_create.append({
                    "entity_data": entity_data,
                    "record_id": int(project.external_id),  # Convert to int
                    "table_name": "projects"
                })
                
            except Exception as e:
                print(f"❌ Error preparing project {project.key}: {e}")
        
        print(f"\n📤 Sending {len(entities_to_create)} projects to backend...")
        
        # Get auth token
        try:
            auth_token = _get_job_auth_token(1)
            print(f"✅ Got auth token: {auth_token[:20]}...")
        except Exception as e:
            print(f"❌ Failed to get auth token: {e}")
            return
        
        # Call bulk vector creation
        try:
            result = await bulk_store_entity_vectors_for_etl(entities_to_create, auth_token=auth_token)
            
            print(f"\n📊 Results:")
            print(f"   Success: {result.success}")
            print(f"   Vectors stored: {result.vectors_stored}")
            print(f"   Vectors failed: {result.vectors_failed}")
            print(f"   Processing time: {result.processing_time:.2f}s")
            print(f"   Provider used: {result.provider_used}")
            
            if result.error:
                print(f"   Error: {result.error}")
                
        except Exception as e:
            print(f"❌ Error calling backend: {e}")
            import traceback
            traceback.print_exc()

async def test_changelogs_vectorization():
    """Test vectorization with real changelog data from database"""
    print("\n🧪 Testing Changelogs AI Vectorization...")
    print("=" * 60)
    
    database = get_database()
    with database.get_read_session_context() as session:
        
        # Get first 2 changelogs from database
        changelogs = session.query(Changelog).filter(Changelog.tenant_id == 1).limit(2).all()
        
        if not changelogs:
            print("❌ No changelogs found in database")
            return
            
        print(f"Found {len(changelogs)} changelogs to test:")
        for changelog in changelogs:
            print(f"   • ID: {changelog.external_id}, From: {changelog.from_status_id} -> To: {changelog.to_status_id}")
            print(f"     Change date: {changelog.transition_change_date}, Changed by: {changelog.changed_by}")
        
        # Prepare entities like ETL does
        entities_to_create = []
        for changelog in changelogs:
            try:
                # Create entity data for AI processing (avoiding datetime serialization)
                entity_data = {
                    "external_id": changelog.external_id,
                    "from_status_id": changelog.from_status_id,
                    "to_status_id": changelog.to_status_id,
                    "changed_by": changelog.changed_by,
                    "transition_change_date": changelog.transition_change_date.isoformat() if changelog.transition_change_date else None  # Convert datetime to string
                }
                
                # Remove None values to create cleaner text content
                entity_data = {k: v for k, v in entity_data.items() if v is not None}
                
                entities_to_create.append({
                    "entity_data": entity_data,
                    "record_id": int(changelog.external_id),  # Convert to int
                    "table_name": "changelogs"
                })
                
            except Exception as e:
                print(f"❌ Error preparing changelog {changelog.external_id}: {e}")
        
        print(f"\n📤 Sending {len(entities_to_create)} changelogs to backend...")
        
        # Get auth token
        try:
            auth_token = _get_job_auth_token(1)
            print(f"✅ Got auth token: {auth_token[:20]}...")
        except Exception as e:
            print(f"❌ Failed to get auth token: {e}")
            return
        
        # Call bulk vector creation
        try:
            result = await bulk_store_entity_vectors_for_etl(entities_to_create, auth_token=auth_token)
            
            print(f"\n📊 Results:")
            print(f"   Success: {result.success}")
            print(f"   Vectors stored: {result.vectors_stored}")
            print(f"   Vectors failed: {result.vectors_failed}")
            print(f"   Processing time: {result.processing_time:.2f}s")
            print(f"   Provider used: {result.provider_used}")
            
            if result.error:
                print(f"   Error: {result.error}")
                
        except Exception as e:
            print(f"❌ Error calling backend: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """Run all tests"""
    print("🚀 ETL AI Vectorization Test Script")
    print("=" * 60)
    
    # Test projects first
    await test_projects_vectorization()
    
    # Test changelogs
    await test_changelogs_vectorization()
    
    print("\n✅ Test script completed!")

if __name__ == "__main__":
    asyncio.run(main())
