#!/usr/bin/env python3
"""
Fix Missing Logos Script
Description: Clears logo_filename for integrations where the logo file doesn't exist
Author: Pulse Platform Team
Date: 2025-09-09
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

# Add the backend service to the path to access database configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def get_database_connection():
    """Get database connection using backend service configuration."""
    try:
        from app.core.config import Settings
        config = Settings()

        connection = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DATABASE,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
            cursor_factory=RealDictCursor
        )
        return connection
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        raise

def main():
    """Fix missing logo files by clearing logo_filename for non-existent files."""
    print("🔧 Fixing missing logo files...")
    
    connection = get_database_connection()
    cursor = connection.cursor()
    
    try:
        # Get all integrations with logo filenames
        cursor.execute("""
            SELECT i.id, i.provider, i.logo_filename, t.assets_folder
            FROM integrations i
            JOIN tenants t ON i.tenant_id = t.id
            WHERE i.logo_filename IS NOT NULL AND i.logo_filename != ''
        """)
        
        integrations = cursor.fetchall()
        print(f"📋 Found {len(integrations)} integrations with logo filenames")
        
        # Check if logo files exist
        etl_service_path = Path(__file__).parent.parent.parent / "etl-service"
        missing_logos = []
        
        for integration in integrations:
            logo_path = etl_service_path / "static" / "assets" / integration['assets_folder'] / "integrations" / integration['logo_filename']
            
            if not logo_path.exists():
                missing_logos.append(integration)
                print(f"❌ Missing logo: {integration['provider']} -> {logo_path}")
            else:
                print(f"✅ Logo exists: {integration['provider']} -> {logo_path}")
        
        if missing_logos:
            print(f"\n🔧 Clearing logo_filename for {len(missing_logos)} integrations with missing files...")
            
            for integration in missing_logos:
                cursor.execute("""
                    UPDATE integrations 
                    SET logo_filename = NULL, last_updated_at = NOW()
                    WHERE id = %s
                """, (integration['id'],))
                
                print(f"   ✅ Cleared logo_filename for {integration['provider']}")
            
            connection.commit()
            print(f"\n✅ Successfully cleared logo_filename for {len(missing_logos)} integrations")
        else:
            print("\n✅ All logo files exist - no changes needed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    main()
