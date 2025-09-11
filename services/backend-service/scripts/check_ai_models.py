#!/usr/bin/env python3
"""
Quick script to check AI model configurations in the database
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_database_connection():
    """Get database connection using environment variables"""
    try:
        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DATABASE", "pulse_db"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "pulse")
        )
        return connection
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)

def main():
    print("🔍 Checking AI Model Configurations")
    print("=" * 50)
    
    # Get database connection
    conn = get_database_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Check AI provider integrations
            cursor.execute("""
                SELECT 
                    i.id,
                    i.provider,
                    i.ai_model,
                    i.fallback_integration_id,
                    t.name as tenant_name,
                    fallback.ai_model as fallback_model
                FROM integrations i
                JOIN tenants t ON i.tenant_id = t.id
                LEFT JOIN integrations fallback ON i.fallback_integration_id = fallback.id
                WHERE i.type = 'ai_provider'
                ORDER BY t.name, i.id;
            """)
            
            results = cursor.fetchall()
            
            if not results:
                print("❌ No AI provider integrations found!")
                return
            
            print(f"✅ Found {len(results)} AI provider integrations:")
            print()
            
            current_tenant = None
            for row in results:
                if row['tenant_name'] != current_tenant:
                    current_tenant = row['tenant_name']
                    print(f"📋 {current_tenant} Tenant:")
                
                print(f"   ID {row['id']}: {row['provider']}")
                print(f"      🤖 Model: {row['ai_model']}")
                if row['fallback_integration_id']:
                    print(f"      🔄 Fallback: ID {row['fallback_integration_id']} ({row['fallback_model']})")
                else:
                    print(f"      🔄 Fallback: None")
                print()
                
    except Exception as e:
        print(f"❌ Error checking AI models: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
