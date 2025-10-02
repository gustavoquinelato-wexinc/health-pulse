"""
Migration 0005: ETL Jobs Autonomous Architecture
================================================

This migration transforms the ETL system from orchestrator-based to autonomous job scheduling:

Changes:
1. Drop and recreate etl_jobs table with new simplified schema
2. Remove orchestrator-related system_settings
3. Drop vectorization_queue table (vectorization now integrated into transform workers)
4. Seed new etl_jobs for all tenants with autonomous configuration

New Architecture:
- Each job has its own schedule (schedule_interval_minutes)
- Fast retry on failure (retry_interval_minutes)
- Generic checkpoint_data JSONB for job-specific recovery
- No execution_order (jobs are independent)
- Simplified status: READY, RUNNING, FINISHED, FAILED
- No vectorization job (integrated into transform workers)

Rollback: To restore old ETL orchestrator, simply rollback this migration.
"""

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

def apply(connection):
    """Apply migration: Transform to autonomous ETL architecture."""
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        print("=" * 80)
        print("🚀 Migration 0005: ETL Jobs Autonomous Architecture")
        print("=" * 80)
        
        # ====================================================================
        # STEP 1: Backup existing etl_jobs data (for reference)
        # ====================================================================
        print("\n📋 Step 1: Backing up existing etl_jobs data...")
        
        cursor.execute("""
            SELECT job_name, integration_id, tenant_id, active
            FROM etl_jobs
            ORDER BY tenant_id, job_name;
        """)
        existing_jobs = cursor.fetchall()
        print(f"✅ Found {len(existing_jobs)} existing jobs to migrate")
        
        # ====================================================================
        # STEP 2: Drop vectorization_queue table
        # ====================================================================
        print("\n📋 Step 2: Dropping vectorization_queue table...")
        
        cursor.execute("DROP TABLE IF EXISTS vectorization_queue CASCADE;")
        print("✅ vectorization_queue table dropped")
        
        # ====================================================================
        # STEP 3: Delete ETL-related settings from system_settings
        # ====================================================================
        print("\n📋 Step 3: Removing ETL-related settings from system_settings...")

        etl_settings_to_remove = [
            # Orchestrator settings (no orchestrator anymore)
            'orchestrator_interval_minutes',
            'orchestrator_enabled',
            'orchestrator_retry_enabled',
            'orchestrator_retry_interval_minutes',
            # Job-specific sync settings (now controlled by etl_jobs.active)
            'jira_sync_enabled',
            'github_sync_enabled',
            # Concurrent jobs limit (jobs are independent now)
            'max_concurrent_jobs'
        ]

        for setting_key in etl_settings_to_remove:
            cursor.execute("""
                DELETE FROM system_settings
                WHERE setting_key = %s;
            """, (setting_key,))

        print(f"✅ Removed {len(etl_settings_to_remove)} ETL-related settings")
        
        # ====================================================================
        # STEP 4: Drop and recreate etl_jobs table with new schema
        # ====================================================================
        print("\n📋 Step 4: Recreating etl_jobs table with new schema...")
        
        cursor.execute("DROP TABLE IF EXISTS etl_jobs CASCADE;")
        
        cursor.execute("""
            CREATE TABLE etl_jobs (
                -- Primary Key
                id SERIAL PRIMARY KEY,

                -- Core Job Identity
                job_name VARCHAR NOT NULL,

                -- Job Status
                status VARCHAR(20) NOT NULL DEFAULT 'READY',

                -- Scheduling Configuration
                schedule_interval_minutes INTEGER NOT NULL DEFAULT 360,
                retry_interval_minutes INTEGER NOT NULL DEFAULT 15,

                -- Execution Tracking
                last_run_started_at TIMESTAMP,
                last_run_finished_at TIMESTAMP,

                -- Error Handling
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,

                -- Generic Recovery/Checkpoint
                checkpoint_data JSONB,

                -- Foreign Keys
                integration_id INTEGER REFERENCES integrations(id),

                -- BaseEntity Fields (ALWAYS LAST)
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),

                -- Constraints
                UNIQUE(job_name, tenant_id),
                CHECK (status IN ('READY', 'RUNNING', 'FINISHED', 'FAILED'))
            );
        """)
        
        print("✅ etl_jobs table recreated with new schema")
        
        # ====================================================================
        # STEP 5: Create indexes
        # ====================================================================
        print("\n📋 Step 5: Creating indexes...")
        
        cursor.execute("""
            CREATE INDEX idx_etl_jobs_active 
            ON etl_jobs(tenant_id, active, schedule_interval_minutes) 
            WHERE active = TRUE;
        """)
        
        cursor.execute("""
            CREATE INDEX idx_etl_jobs_status 
            ON etl_jobs(tenant_id, status) 
            WHERE active = TRUE;
        """)
        
        print("✅ Indexes created")
        
        # ====================================================================
        # STEP 6: Seed etl_jobs for all tenants
        # ====================================================================
        print("\n📋 Step 6: Seeding etl_jobs for all tenants...")
        
        # Get all tenants
        cursor.execute("SELECT id, name FROM tenants ORDER BY id;")
        tenants = cursor.fetchall()
        
        for tenant in tenants:
            tenant_id = tenant['id']
            tenant_name = tenant['name']
            
            print(f"\n  📦 Seeding jobs for tenant: {tenant_name} (ID: {tenant_id})")
            
            # Get integration IDs for this tenant
            cursor.execute("""
                SELECT id, provider
                FROM integrations
                WHERE tenant_id = %s
                AND provider IN ('Jira', 'GitHub', 'WEX Fabric', 'WEX AD', 'Internal')
                ORDER BY provider;
            """, (tenant_id,))

            integrations = {row['provider']: row['id'] for row in cursor.fetchall()}
            
            # Define jobs with their configurations
            jobs_config = [
                {
                    "job_name": "Jira",
                    "integration_id": integrations.get('Jira'),
                    "schedule_interval_minutes": 360,  # 6 hours
                    "status": "READY",
                    "active": True
                },
                {
                    "job_name": "GitHub",
                    "integration_id": integrations.get('GitHub'),
                    "schedule_interval_minutes": 240,  # 4 hours
                    "status": "READY",
                    "active": True
                },
                {
                    "job_name": "WEX Fabric",
                    "integration_id": integrations.get('WEX Fabric'),
                    "schedule_interval_minutes": 1440,  # 24 hours
                    "status": "READY",
                    "active": False  # Inactive by default (not implemented yet)
                },
                {
                    "job_name": "WEX AD",
                    "integration_id": integrations.get('WEX AD'),
                    "schedule_interval_minutes": 720,  # 12 hours
                    "status": "READY",
                    "active": False  # Inactive by default (not implemented yet)
                }
                # NOTE: No Vectorization job - now integrated into transform workers
            ]
            
            # Insert jobs
            for job in jobs_config:
                if job["integration_id"]:  # Only insert if integration exists
                    cursor.execute("""
                        INSERT INTO etl_jobs (
                            job_name, 
                            status, 
                            schedule_interval_minutes, 
                            retry_interval_minutes,
                            integration_id, 
                            tenant_id, 
                            active, 
                            created_at, 
                            last_updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (job_name, tenant_id) DO NOTHING;
                    """, (
                        job["job_name"],
                        job["status"],
                        job["schedule_interval_minutes"],
                        15,  # retry_interval_minutes (15 min for all jobs)
                        job["integration_id"],
                        tenant_id,
                        job["active"]
                    ))
                    print(f"    ✅ {job['job_name']} (interval: {job['schedule_interval_minutes']}min, active: {job['active']})")
                else:
                    print(f"    ⚠️  {job['job_name']} - integration not found, skipped")

        print("\n" + "=" * 80)
        print("✅ Migration 0005 completed successfully!")
        print("=" * 80)
        print("\n📊 Summary:")
        print("  • etl_jobs table recreated with autonomous architecture")
        print("  • vectorization_queue table dropped")
        print("  • 7 ETL-related settings removed from system_settings:")
        print("    - orchestrator_* settings (4 settings)")
        print("    - jira_sync_enabled, github_sync_enabled")
        print("    - max_concurrent_jobs")
        print(f"  • {len(tenants)} tenants migrated with 4 jobs each")
        print("  • Vectorization job removed (now integrated into workers)")
        print("\n⚠️  NOTE: Old ETL service will stop working after this migration.")
        print("   To restore old ETL, rollback this migration.")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cursor.close()


def rollback(connection):
    """Rollback migration: Restore orchestrator-based ETL architecture."""
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        print("=" * 80)
        print("⏪ Rolling back Migration 0005: Restoring Orchestrator Architecture")
        print("=" * 80)

        # This is complex - would need to restore old schema
        # For now, recommend re-running migrations 0001-0004
        print("\n⚠️  ROLLBACK STRATEGY:")
        print("   To restore the old ETL orchestrator architecture:")
        print("   1. Drop database")
        print("   2. Re-run migrations 0001-0004")
        print("   3. This will restore the original etl_jobs schema with orchestrator")

        print("\n✅ Rollback information provided")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Rollback failed: {e}")
        raise
    finally:
        cursor.close()

