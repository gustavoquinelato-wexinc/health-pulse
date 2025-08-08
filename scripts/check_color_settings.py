#!/usr/bin/env python3
"""
Check Custom Color Settings in Database

This script verifies if the custom color settings were properly created in the database.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def check_color_settings():
    """Check if custom color settings exist in database"""
    try:
        # Add ETL service to path for database config
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'etl-service'))

        from app.core.config import Settings
        import psycopg2

        # Get database connection using ETL service configuration
        settings = Settings()
        conn = psycopg2.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            database=settings.DATABASE_NAME,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD
        )

        cursor = conn.cursor()
        
        print("🔍 Checking custom color settings in database...")
        
        # Check clients table
        cursor.execute("SELECT id, name FROM clients ORDER BY id;")
        clients = cursor.fetchall()
        print(f"\n📋 Available clients:")
        for client in clients:
            print(f"   ID: {client[0]}, Name: {client[1]}")
        
        # Check custom color settings
        cursor.execute("""
            SELECT setting_key, setting_value, description, client_id 
            FROM system_settings 
            WHERE setting_key LIKE 'custom_color%' 
            ORDER BY setting_key
        """)
        
        color_settings = cursor.fetchall()
        
        if color_settings:
            print(f"\n✅ Found {len(color_settings)} custom color settings:")
            for setting in color_settings:
                print(f"   {setting[0]}: {setting[1]} (Client ID: {setting[3]})")
                print(f"      Description: {setting[2]}")
        else:
            print("\n❌ No custom color settings found in database")
            
        # Check all system settings
        cursor.execute("SELECT COUNT(*) FROM system_settings;")
        total_settings = cursor.fetchone()[0]
        print(f"\n📊 Total system settings in database: {total_settings}")
        
        cursor.close()
        conn.close()
        
        return len(color_settings) > 0
        
    except Exception as e:
        print(f"❌ Error checking color settings: {e}")
        return False

if __name__ == "__main__":
    check_color_settings()
