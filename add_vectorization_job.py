#!/usr/bin/env python3
"""
Script to add the Vectorization job to existing tenants.

This script adds the new Vectorization job to all existing tenants
that don't already have it.
"""

import sys
import os

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

def add_vectorization_job():
    """Add vectorization job to all tenants."""
    
    try:
        from app.core.database import get_database
        from app.models.unified_models import JobSchedule, Integration, Tenant
        
        database = get_database()
        
        with database.get_write_session_context() as session:
            # Get all tenants
            tenants = session.query(Tenant).filter(Tenant.active == True).all()
            
            print(f"Found {len(tenants)} active tenants")
            
            for tenant in tenants:
                print(f"\nProcessing tenant: {tenant.name} (ID: {tenant.id})")
                
                # Check if vectorization job already exists
                existing_job = session.query(JobSchedule).filter(
                    JobSchedule.tenant_id == tenant.id,
                    JobSchedule.job_name == 'Vectorization'
                ).first()
                
                if existing_job:
                    print(f"  ✅ Vectorization job already exists (ID: {existing_job.id})")
                    continue
                
                # Find AI provider integration for this tenant
                ai_integration = session.query(Integration).filter(
                    Integration.tenant_id == tenant.id,
                    Integration.type == 'AI Provider'
                ).first()
                
                if not ai_integration:
                    print(f"  ⚠️  No AI Provider integration found - creating job without integration")
                    ai_integration_id = None
                else:
                    ai_integration_id = ai_integration.id
                    print(f"  ✅ Found AI Provider integration (ID: {ai_integration_id})")
                
                # Create vectorization job
                vectorization_job = JobSchedule(
                    job_name='Vectorization',
                    execution_order=5,  # After all other jobs
                    status='NOT_STARTED',
                    integration_id=ai_integration_id,
                    tenant_id=tenant.id,
                    active=True
                )
                
                session.add(vectorization_job)
                print(f"  ✅ Added Vectorization job (order: 5, status: NOT_STARTED)")
            
            # Commit all changes
            session.commit()
            print(f"\n🎉 Successfully added Vectorization job to all tenants!")
            
            # Verify the jobs were added
            print(f"\n📋 Verification:")
            for tenant in tenants:
                jobs = session.query(JobSchedule).filter(
                    JobSchedule.tenant_id == tenant.id
                ).order_by(JobSchedule.execution_order).all()
                
                print(f"\n{tenant.name} jobs:")
                for job in jobs:
                    print(f"  {job.execution_order}. {job.job_name} - {job.status}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error adding vectorization job: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🔧 Adding Vectorization Job to Existing Tenants")
    print("=" * 50)
    
    success = add_vectorization_job()
    
    if success:
        print("\n✅ Vectorization job added successfully!")
        print("\n📋 Next steps:")
        print("   1. The vectorization job is now available in the job sequence")
        print("   2. It will run after all other jobs complete")
        print("   3. You can manually trigger it via the orchestrator")
        print("   4. ETL jobs will now only queue data, not trigger processing")
        sys.exit(0)
    else:
        print("\n❌ Failed to add vectorization job")
        sys.exit(1)
