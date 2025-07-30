#!/usr/bin/env python3
"""
Test script to check color schema settings in the database
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

from app.core.database import get_database
from app.models.unified_models import SystemSettings

def main():
    print("🔍 Checking color schema settings in database...")
    
    try:
        database = get_database()
        
        with database.get_session() as session:
            # Get all color-related settings
            color_settings = session.query(SystemSettings).filter(
                SystemSettings.setting_key.like('%color%')
            ).all()
            
            print(f"\n📊 Found {len(color_settings)} color-related settings:")
            
            for setting in color_settings:
                print(f"   🎨 {setting.setting_key}: {setting.setting_value} (Client: {setting.client_id})")
            
            # Check for color schema mode
            schema_mode = session.query(SystemSettings).filter(
                SystemSettings.setting_key == 'color_schema_mode'
            ).all()
            
            print(f"\n🎯 Color schema mode settings:")
            for setting in schema_mode:
                print(f"   📋 Client {setting.client_id}: {setting.setting_value}")
            
            # Check for theme mode
            theme_mode = session.query(SystemSettings).filter(
                SystemSettings.setting_key == 'theme_mode'
            ).all()
            
            print(f"\n🌙 Theme mode settings:")
            for setting in theme_mode:
                print(f"   🎭 Client {setting.client_id}: {setting.setting_value}")
                
            if not color_settings and not schema_mode and not theme_mode:
                print("\n❌ No color or theme settings found in database!")
                print("   This explains why ETL is using default colors.")
                
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    main()
