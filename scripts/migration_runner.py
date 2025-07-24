#!/usr/bin/env python3
"""
Migration Runner Utility
Description: Manages and executes database migrations for the Pulse Platform
Author: Pulse Platform Team
Date: 2025-07-21

This utility provides a centralized way to:
- Apply multiple migrations in sequence
- Rollback to specific migration versions
- Check migration status across the system
- Manage migration dependencies and ordering
"""

import os
import sys
import argparse
import importlib.util
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import re

# Add the ETL service to the path to access database configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'etl-service'))

def get_database_connection():
    """Get database connection using ETL service configuration."""
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
        connection.autocommit = False  # Use transactions
        return connection
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

def create_migration_table(connection):
    """Create migration tracking table if it doesn't exist."""
    cursor = connection.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migration_history (
            id SERIAL PRIMARY KEY,
            migration_number VARCHAR(10) NOT NULL UNIQUE,
            migration_name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP DEFAULT NOW(),
            rollback_at TIMESTAMP NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'applied'
        );
    """)
    
    connection.commit()

def get_migration_files():
    """Get list of available migration files."""
    migration_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    migration_files = []
    
    for filename in os.listdir(migration_dir):
        if filename.startswith(('001_', '002_', '003_')) and filename.endswith('.py'):
            migration_number = filename[:3]
            migration_name = filename[4:-3].replace('_', ' ').title()
            migration_files.append({
                'number': migration_number,
                'name': migration_name,
                'filename': filename,
                'path': os.path.join(migration_dir, filename)
            })
    
    return sorted(migration_files, key=lambda x: x['number'])

def load_migration_module(migration_path):
    """Dynamically load a migration module."""
    spec = importlib.util.spec_from_file_location("migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def get_applied_migrations(connection):
    """Get list of applied migrations from database."""
    cursor = connection.cursor()
    
    try:
        cursor.execute("""
            SELECT migration_number, migration_name, applied_at, status
            FROM migration_history 
            WHERE status = 'applied'
            ORDER BY migration_number;
        """)
        return cursor.fetchall()
    except psycopg2.errors.UndefinedTable:
        # Migration table doesn't exist yet
        return []

def record_migration(connection, migration_number, migration_name, status):
    """Record migration application or rollback."""
    cursor = connection.cursor()

    try:
        if status == 'applied':
            cursor.execute("""
                INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
                VALUES (%s, %s, NOW(), 'applied')
                ON CONFLICT (migration_number)
                DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
            """, (migration_number, migration_name))
        elif status == 'rolled_back':
            cursor.execute("""
                UPDATE migration_history
                SET rollback_at = NOW(), status = 'rolled_back'
                WHERE migration_number = %s;
            """, (migration_number,))

        connection.commit()
    except psycopg2.errors.UndefinedTable:
        # Migration history table doesn't exist (expected when rolling back everything)
        print(f"📋 Migration history table doesn't exist - rollback record not maintained")
        connection.rollback()

def show_status(connection):
    """Show status of all migrations."""
    print("📋 Migration Status Report")
    print("=" * 50)
    
    # Create migration table if needed
    create_migration_table(connection)
    
    # Get available and applied migrations
    available_migrations = get_migration_files()
    applied_migrations = {m['migration_number']: m for m in get_applied_migrations(connection)}
    
    if not available_migrations:
        print("⚠️  No migration files found.")
        return
    
    for migration in available_migrations:
        number = migration['number']
        name = migration['name']
        
        if number in applied_migrations:
            applied_info = applied_migrations[number]
            status = "✅ Applied"
            date = applied_info['applied_at'].strftime("%Y-%m-%d %H:%M:%S")
            print(f"{number}: {name:<30} {status} ({date})")
        else:
            print(f"{number}: {name:<30} ⏸️  Pending")
    
    print("=" * 50)
    applied_count = len(applied_migrations)
    total_count = len(available_migrations)
    pending_count = total_count - applied_count
    print(f"📊 Summary: {applied_count} applied, {pending_count} pending, {total_count} total")

def apply_migration(connection, migration_file):
    """Apply a single migration."""
    print(f"🚀 Applying Migration {migration_file['number']}: {migration_file['name']}")
    
    try:
        # Load and execute migration
        module = load_migration_module(migration_file['path'])
        module.apply(connection)
        
        # Record successful application
        record_migration(connection, migration_file['number'], migration_file['name'], 'applied')
        print(f"✅ Migration {migration_file['number']} applied successfully")
        
    except Exception as e:
        print(f"❌ Error applying migration {migration_file['number']}: {e}")
        raise

def rollback_migration(connection, migration_file):
    """Rollback a single migration."""
    print(f"🔄 Rolling back Migration {migration_file['number']}: {migration_file['name']}")
    
    try:
        # Load and execute rollback
        module = load_migration_module(migration_file['path'])
        module.rollback(connection)
        
        # Record successful rollback
        record_migration(connection, migration_file['number'], migration_file['name'], 'rolled_back')
        print(f"✅ Migration {migration_file['number']} rolled back successfully")
        
    except Exception as e:
        print(f"❌ Error rolling back migration {migration_file['number']}: {e}")
        raise

def apply_all_migrations(connection):
    """Apply all pending migrations."""
    print("🚀 Applying all pending migrations...")
    
    # Create migration table if needed
    create_migration_table(connection)
    
    # Get available and applied migrations
    available_migrations = get_migration_files()
    applied_migrations = {m['migration_number'] for m in get_applied_migrations(connection)}
    
    pending_migrations = [m for m in available_migrations if m['number'] not in applied_migrations]
    
    if not pending_migrations:
        print("✅ All migrations are already applied.")
        return
    
    for migration in pending_migrations:
        apply_migration(connection, migration)
    
    print(f"✅ Applied {len(pending_migrations)} migration(s) successfully!")

def rollback_to_migration(connection, target_migration):
    """Rollback to a specific migration."""
    print(f"🔄 Rolling back to migration {target_migration}...")

    # Get available and applied migrations
    available_migrations = get_migration_files()
    applied_migrations = get_applied_migrations(connection)

    # Find migrations to rollback (in reverse order)
    migrations_to_rollback = []

    # Special case: rollback to "000" means rollback everything
    if target_migration == "000":
        for migration in reversed(available_migrations):
            if migration['number'] in [m['migration_number'] for m in applied_migrations]:
                migrations_to_rollback.append(migration)
    else:
        # Normal case: rollback until we reach the target migration
        for migration in reversed(available_migrations):
            if migration['number'] in [m['migration_number'] for m in applied_migrations]:
                if migration['number'] == target_migration:
                    break
                migrations_to_rollback.append(migration)

    if not migrations_to_rollback:
        print(f"✅ Already at migration {target_migration} or no rollbacks needed.")
        return

    for migration in migrations_to_rollback:
        rollback_migration(connection, migration)

    print(f"✅ Rolled back {len(migrations_to_rollback)} migration(s) successfully!")

def get_next_migration_number():
    """Get the next migration number by finding the highest existing number."""
    migration_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    max_number = 0

    for filename in os.listdir(migration_dir):
        if filename.endswith('.py') and not filename.startswith('migration_runner'):
            # Extract number from filename like "001_initial_schema.py"
            match = re.match(r'^(\d+)_', filename)
            if match:
                number = int(match.group(1))
                max_number = max(max_number, number)

    return max_number + 1

def create_new_migration(migration_name):
    """Create a new migration file with template."""
    # Get next migration number
    migration_number = f"{get_next_migration_number():03d}"

    # Create filename
    filename = f"{migration_number}_{migration_name.lower().replace(' ', '_')}.py"
    migration_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    filepath = os.path.join(migration_dir, filename)

    # Check if file already exists
    if os.path.exists(filepath):
        print(f"❌ Migration file {filename} already exists!")
        return

    # Create migration template
    template = f'''#!/usr/bin/env python3
"""
Migration {migration_number}: {migration_name}
Description: [Add description of what this migration does]
Author: [Your Name]
Date: {datetime.now().strftime("%Y-%m-%d")}
"""

import os
import sys
import argparse
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the ETL service to the path to access database configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'etl-service'))

def get_database_connection():
    """Get database connection using ETL service configuration."""
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
        print(f"ERROR: Failed to connect to database: {{e}}")
        raise

def apply(connection):
    """Apply the migration."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        print("Applying migration changes...")

        # TODO: Add your migration logic here
        # Example:
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS example_table (
        #         id SERIAL PRIMARY KEY,
        #         name VARCHAR NOT NULL,
        #         created_at TIMESTAMP DEFAULT NOW()
        #     );
        # """)

        # Record this migration as applied
        cursor.execute("""
            INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
            VALUES (%s, %s, NOW(), 'applied')
            ON CONFLICT (migration_number)
            DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
        """, ('{migration_number}', '{migration_name}'))

        connection.commit()
        print(f"SUCCESS: Migration {migration_number} applied successfully")

    except Exception as e:
        connection.rollback()
        print(f"ERROR: Error applying migration: {{e}}")
        raise

def rollback(connection):
    """Rollback the migration."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        print("Rolling back migration changes...")

        # TODO: Add your rollback logic here
        # Example:
        # cursor.execute("DROP TABLE IF EXISTS example_table;")

        # Record this migration as rolled back
        cursor.execute("""
            UPDATE migration_history
            SET rollback_at = NOW(), status = 'rolled_back'
            WHERE migration_number = %s;
        """, ('{migration_number}',))

        connection.commit()
        print(f"SUCCESS: Migration {migration_number} rolled back successfully")

    except Exception as e:
        connection.rollback()
        print(f"ERROR: Error rolling back migration: {{e}}")
        raise

def check_status(connection):
    """Check if this migration has been applied."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT migration_number, migration_name, applied_at, rollback_at, status
            FROM migration_history
            WHERE migration_number = %s;
        """, ('{migration_number}',))

        result = cursor.fetchone()
        if result:
            status = result['status']
            if status == 'applied':
                print(f"SUCCESS: Migration {migration_number} is applied ({{result['applied_at']}})")
            elif status == 'rolled_back':
                print(f"ROLLBACK: Migration {migration_number} was rolled back ({{result['rollback_at']}})")
        else:
            print(f"PENDING: Migration {migration_number} has not been applied")

    except Exception as e:
        print(f"ERROR: Error checking migration status: {{e}}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration {migration_number}: {migration_name}")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    parser.add_argument("--status", action="store_true", help="Check migration status")

    args = parser.parse_args()

    if not any([args.apply, args.rollback, args.status]):
        parser.print_help()
        sys.exit(1)

    try:
        conn = get_database_connection()

        if args.apply:
            apply(conn)
        elif args.rollback:
            rollback(conn)
        elif args.status:
            check_status(conn)

        conn.close()

    except Exception as e:
        print(f"ERROR: Migration failed: {{e}}")
        sys.exit(1)
'''

    # Write the template to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"SUCCESS: Created new migration: {filename}")
    print(f"Location: {filepath}")
    print(f"Edit the file to add your migration logic")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pulse Platform Migration Runner")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--apply-all", action="store_true", help="Apply all pending migrations")
    parser.add_argument("--rollback-to", metavar="MIGRATION", help="Rollback to specific migration (e.g., 001)")
    parser.add_argument("--new", type=str, metavar="NAME", help="Create new migration with given name")

    args = parser.parse_args()

    if not any([args.status, args.apply_all, args.rollback_to, args.new]):
        parser.print_help()
        sys.exit(1)

    # Handle --new command (doesn't need database connection)
    if args.new:
        try:
            create_new_migration(args.new)
            sys.exit(0)
        except Exception as e:
            print(f"❌ Failed to create migration: {e}")
            sys.exit(1)

    # Other commands need database connection
    conn = get_database_connection()

    try:
        if args.status:
            show_status(conn)
        elif args.apply_all:
            apply_all_migrations(conn)
        elif args.rollback_to:
            rollback_to_migration(conn, args.rollback_to)

    finally:
        conn.close()
