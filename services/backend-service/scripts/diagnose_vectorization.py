"""
Diagnostic script to check vectorization status
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_database
from sqlalchemy import text

def main():
    database = get_database()
    
    with database.get_read_session_context() as session:
        print("=" * 80)
        print("VECTORIZATION DIAGNOSTIC REPORT")
        print("=" * 80)
        
        # 1. Count entities in database
        print("\n1. ENTITIES IN DATABASE:")
        print("-" * 80)
        
        # Projects
        result = session.execute(text("SELECT COUNT(*) FROM projects WHERE tenant_id = 1 AND active = true"))
        projects_count = result.scalar()
        print(f"   Projects: {projects_count}")
        
        # WITs
        result = session.execute(text("SELECT COUNT(*) FROM wits WHERE tenant_id = 1 AND active = true"))
        wits_count = result.scalar()
        print(f"   WITs: {wits_count}")
        
        # Statuses
        result = session.execute(text("SELECT COUNT(*) FROM statuses WHERE tenant_id = 1 AND active = true"))
        statuses_count = result.scalar()
        print(f"   Statuses: {statuses_count}")
        
        print(f"\n   TOTAL EXPECTED: {projects_count + wits_count + statuses_count}")
        
        # 2. Count vectors in qdrant_vectors bridge table
        print("\n2. VECTORS IN BRIDGE TABLE (qdrant_vectors):")
        print("-" * 80)
        
        result = session.execute(text("""
            SELECT table_name, COUNT(*) as count
            FROM qdrant_vectors
            WHERE tenant_id = 1 AND active = true
            GROUP BY table_name
            ORDER BY table_name
        """))
        
        total_bridge = 0
        for row in result:
            print(f"   {row.table_name}: {row.count}")
            total_bridge += row.count
        
        print(f"\n   TOTAL IN BRIDGE: {total_bridge}")
        
        # 3. Check vectorization queue (RabbitMQ - not in database)
        print("\n3. VECTORIZATION QUEUE STATUS:")
        print("-" * 80)
        print("   Using RabbitMQ - queue status not available in database")
        
        # 4. Check for missing WITs
        print("\n4. MISSING WITS (in database but not in qdrant_vectors):")
        print("-" * 80)
        
        result = session.execute(text("""
            SELECT w.id, w.external_id, w.original_name
            FROM wits w
            LEFT JOIN qdrant_vectors qv ON qv.table_name = 'wits' AND qv.record_id = w.id AND qv.tenant_id = w.tenant_id
            WHERE w.tenant_id = 1 AND w.active = true AND qv.id IS NULL
            ORDER BY w.id
        """))
        
        missing_wits = list(result)
        if missing_wits:
            for row in missing_wits:
                print(f"   WIT id={row.id}, external_id={row.external_id}, name={row.original_name}")
        else:
            print("   No missing WITs")
        
        # 5. Check for missing projects
        print("\n5. MISSING PROJECTS (in database but not in qdrant_vectors):")
        print("-" * 80)
        
        result = session.execute(text("""
            SELECT p.id, p.external_id, p.key, p.name
            FROM projects p
            LEFT JOIN qdrant_vectors qv ON qv.table_name = 'projects' AND qv.record_id = p.id AND qv.tenant_id = p.tenant_id
            WHERE p.tenant_id = 1 AND p.active = true AND qv.id IS NULL
            ORDER BY p.id
        """))
        
        missing_projects = list(result)
        if missing_projects:
            for row in missing_projects:
                print(f"   Project id={row.id}, external_id={row.external_id}, key={row.key}, name={row.name}")
        else:
            print("   No missing projects")
        
        # 6. Check WITs with missing wits_mapping_id
        print("\n6. WITS WITH MISSING wits_mapping_id:")
        print("-" * 80)
        
        result = session.execute(text("""
            SELECT id, external_id, original_name, wits_mapping_id
            FROM wits
            WHERE tenant_id = 1 AND active = true AND wits_mapping_id IS NULL
            ORDER BY id
        """))
        
        missing_mapping = list(result)
        if missing_mapping:
            for row in missing_mapping:
                print(f"   WIT id={row.id}, external_id={row.external_id}, name={row.original_name}, mapping_id={row.wits_mapping_id}")
        else:
            print("   All WITs have wits_mapping_id")
        
        # 7. Check raw_extraction_data
        print("\n7. RAW EXTRACTION DATA:")
        print("-" * 80)
        
        result = session.execute(text("""
            SELECT endpoint, status, COUNT(*) as count
            FROM raw_extraction_data
            WHERE tenant_id = 1
            GROUP BY endpoint, status
            ORDER BY endpoint, status
        """))
        
        for row in result:
            print(f"   {row.endpoint} - {row.status}: {row.count}")
        
        print("\n" + "=" * 80)
        print("END OF REPORT")
        print("=" * 80)

if __name__ == "__main__":
    main()

