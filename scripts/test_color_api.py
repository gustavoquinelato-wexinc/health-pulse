#!/usr/bin/env python3
"""
Test Color Schema API

This script tests the color schema API endpoints to verify they're working correctly.
"""

import sys
import os
import requests

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def test_color_api():
    """Test the color schema API endpoints"""
    
    # Backend service URL
    backend_url = "http://localhost:3001"
    
    print("🧪 Testing Color Schema API...")
    
    try:
        # Test GET endpoint (without auth for now)
        print("\n1️⃣ Testing GET /api/v1/admin/color-schema")
        response = requests.get(f"{backend_url}/api/v1/admin/color-schema")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success! Response: {data}")
            
            if 'colors' in data:
                colors = data['colors']
                print(f"   🎨 Colors found:")
                for color_key, color_value in colors.items():
                    print(f"      {color_key}: {color_value}")
        elif response.status_code == 401:
            print(f"   ⚠️  Authentication required (expected)")
        else:
            print(f"   ❌ Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Connection failed - is the backend service running on port 3001?")
    except Exception as e:
        print(f"   ❌ Error: {e}")

def check_database_directly():
    """Check the database directly to verify colors are there"""
    print("\n2️⃣ Checking database directly...")
    
    try:
        # Add ETL service to path for database config
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'etl-service'))
        
        from app.core.config import Settings
        import psycopg2
        
        # Get database connection
        settings = Settings()
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DATABASE,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD
        )
        
        cursor = conn.cursor()

        # Check migration history
        cursor.execute("""
            SELECT migration_number, migration_name, status, applied_at
            FROM migration_history
            ORDER BY applied_at DESC
        """)

        migrations = cursor.fetchall()
        print(f"   📋 Migration history:")
        for migration in migrations:
            print(f"      {migration[0]}: {migration[1]} - {migration[2]} at {migration[3]}")

        # Check all system settings
        cursor.execute("SELECT COUNT(*) FROM system_settings;")
        total_settings = cursor.fetchone()[0]
        print(f"   📊 Total system settings: {total_settings}")

        # Check custom color settings
        cursor.execute("""
            SELECT setting_key, setting_value, description
            FROM system_settings
            WHERE setting_key LIKE 'custom_color%'
            ORDER BY setting_key
        """)

        color_settings = cursor.fetchall()

        if color_settings:
            print(f"   ✅ Found {len(color_settings)} custom color settings in database:")
            for setting in color_settings:
                print(f"      {setting[0]}: {setting[1]}")
        else:
            print("   ❌ No custom color settings found in database")

            # Check if there are ANY system settings
            cursor.execute("SELECT setting_key, setting_value FROM system_settings LIMIT 5;")
            any_settings = cursor.fetchall()
            if any_settings:
                print("   📋 Sample system settings:")
                for setting in any_settings:
                    print(f"      {setting[0]}: {setting[1]}")
            else:
                print("   ❌ No system settings found at all!")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Database check failed: {e}")

if __name__ == "__main__":
    test_color_api()
    check_database_directly()
