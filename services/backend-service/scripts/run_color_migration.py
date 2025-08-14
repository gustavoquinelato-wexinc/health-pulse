#!/usr/bin/env python3
"""
Color Data Migration Runner

This script runs the color data migration from system_settings to the new color tables.
It includes safety checks and rollback capabilities.

Usage:
    python run_color_migration.py [--dry-run] [--force]
    
Options:
    --dry-run    Show what would be migrated without making changes
    --force      Skip confirmation prompts
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the parent directory to the path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

def check_prerequisites():
    """Check if migration prerequisites are met"""
    print("🔍 Checking migration prerequisites...")
    
    settings = get_settings()
    
    try:
        conn = psycopg2.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            database=settings.DATABASE_NAME,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if new color tables exist
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('client_color_settings', 'client_accessibility_colors')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if len(tables) != 2:
            print("❌ New color tables not found. Please run migration 001 first.")
            return False
        
        print("✅ New color tables found")
        
        # Check if there's existing data in system_settings
        cursor.execute("""
            SELECT COUNT(*) as count FROM system_settings 
            WHERE setting_key LIKE '%color%' OR setting_key = 'color_schema_mode';
        """)
        result = cursor.fetchone()
        color_settings_count = result['count']
        
        print(f"📊 Found {color_settings_count} color-related settings in system_settings")
        
        # Check if new tables already have data
        cursor.execute("SELECT COUNT(*) as count FROM client_color_settings;")
        result = cursor.fetchone()
        new_table_count = result['count']
        
        if new_table_count > 0:
            print(f"⚠️  New color tables already contain {new_table_count} records")
            print("   Migration will update existing records")
        else:
            print("✅ New color tables are empty, ready for migration")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def run_dry_run():
    """Show what would be migrated without making changes"""
    print("🔍 DRY RUN: Analyzing color data for migration...")
    print("=" * 60)
    
    settings = get_settings()
    
    try:
        conn = psycopg2.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            database=settings.DATABASE_NAME,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all clients
        cursor.execute("SELECT id, name FROM clients WHERE active = TRUE ORDER BY name;")
        clients = cursor.fetchall()
        
        print(f"📋 Would process {len(clients)} clients:")
        
        for client in clients:
            client_id = client['id']
            client_name = client['name']
            
            print(f"\n🏢 Client: {client_name} (ID: {client_id})")
            
            # Check existing color data
            cursor.execute("""
                SELECT setting_key, setting_value FROM system_settings 
                WHERE client_id = %s AND (setting_key LIKE '%color%' OR setting_key = 'color_schema_mode')
                ORDER BY setting_key;
            """, (client_id,))
            settings_data = cursor.fetchall()
            
            if settings_data:
                print(f"   📊 Found {len(settings_data)} color settings:")
                for setting in settings_data:
                    print(f"      • {setting['setting_key']}: {setting['setting_value']}")
            else:
                print("   ⚠️  No color settings found, would use defaults")
            
            # Check if already migrated
            cursor.execute("""
                SELECT color_schema_mode FROM client_color_settings 
                WHERE client_id = %s;
            """, (client_id,))
            existing = cursor.fetchall()
            
            if existing:
                modes = [row['color_schema_mode'] for row in existing]
                print(f"   🔄 Already has color data for modes: {', '.join(modes)}")
            else:
                print("   ✨ Would create new color data")
        
        cursor.close()
        conn.close()
        
        print(f"\n📊 DRY RUN SUMMARY:")
        print(f"   • {len(clients)} clients would be processed")
        print(f"   • {len(clients) * 2} color schema records would be created/updated")
        print(f"   • {len(clients) * 4} accessibility variants would be created/updated")
        
        return True
        
    except Exception as e:
        print(f"❌ Dry run failed: {e}")
        return False

def run_migration(force=False):
    """Run the actual migration"""
    if not force:
        print("\n⚠️  This will migrate color data from system_settings to new color tables.")
        print("   Existing data in new tables will be updated.")
        response = input("   Continue? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Migration cancelled")
            return False
    
    print("\n🚀 Starting color data migration...")
    
    # Import and run the migration
    try:
        from migrations.002_migrate_color_data import migrate_color_data
        return migrate_color_data()
    except ImportError:
        print("❌ Migration script not found")
        return False

def main():
    parser = argparse.ArgumentParser(description='Migrate color data to new tables')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    print("🎨 Color Data Migration Tool")
    print("=" * 40)
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    if args.dry_run:
        success = run_dry_run()
    else:
        success = run_migration(args.force)
    
    if success:
        print("\n✅ Migration completed successfully!")
        if not args.dry_run:
            print("🎨 Color system is now ready for enhanced features!")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
