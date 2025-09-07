"""
Migration 0003: Fix PR Column Names

This migration renames the pull_request_id columns to pr_id in the PR-related tables
to match the SQLAlchemy model definitions.

Tables affected:
- prs_commits: pull_request_id -> pr_id
- prs_reviews: pull_request_id -> pr_id  
- prs_comments: pull_request_id -> pr_id
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

def run_migration():
    """Rename pull_request_id columns to pr_id in PR-related tables"""
    
    # Load environment variables
    load_dotenv()
    
    # Database connection
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'health_pulse'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    print("🔧 Starting Migration 0003: Fix PR Column Names")
    print(f"📡 Connecting to database: {db_config['host']}:{db_config['port']}/{db_config['database']}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ Connected to database")
        
        # Helper function to check if column exists
        def column_exists(table_name: str, column_name: str) -> bool:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                AND column_name = %s;
            """, (table_name, column_name))
            return cursor.fetchone() is not None
        
        # Helper function to rename column if needed
        def rename_column_if_needed(table_name: str, old_column: str, new_column: str):
            if column_exists(table_name, old_column) and not column_exists(table_name, new_column):
                try:
                    cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column};")
                    print(f"✅ Renamed {table_name}.{old_column} to {new_column}")
                except Exception as e:
                    print(f"⚠️ Failed to rename {table_name}.{old_column} to {new_column}: {e}")
            elif column_exists(table_name, new_column):
                print(f"⏭️ Column {table_name}.{new_column} already exists")
            else:
                print(f"⚠️ Column {table_name}.{old_column} does not exist")
        
        print("\n📋 Renaming PR-related columns...")
        
        # Rename columns in PR-related tables
        rename_column_if_needed('prs_commits', 'pull_request_id', 'pr_id')
        rename_column_if_needed('prs_reviews', 'pull_request_id', 'pr_id')
        rename_column_if_needed('prs_comments', 'pull_request_id', 'pr_id')
        
        print("\n📋 Updating foreign key constraints...")
        
        # Helper function to drop constraint if it exists
        def drop_constraint_if_exists(table_name: str, constraint_name: str):
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = %s
                AND constraint_name = %s;
            """, (table_name, constraint_name))
            
            if cursor.fetchone():
                try:
                    cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};")
                    print(f"✅ Dropped constraint {constraint_name} from {table_name}")
                except Exception as e:
                    print(f"⚠️ Failed to drop constraint {constraint_name} from {table_name}: {e}")
        
        # Helper function to add constraint if it doesn't exist
        def add_constraint_if_not_exists(table_name: str, constraint_name: str, constraint_definition: str):
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = %s
                AND constraint_name = %s;
            """, (table_name, constraint_name))
            
            if not cursor.fetchone():
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} {constraint_definition};")
                    print(f"✅ Added constraint {constraint_name} to {table_name}")
                except Exception as e:
                    print(f"⚠️ Failed to add constraint {constraint_name} to {table_name}: {e}")
            else:
                print(f"⏭️ Constraint {constraint_name} already exists on {table_name}")
        
        # Update foreign key constraints to use the new column names
        # Only do this if the columns were actually renamed
        
        if column_exists('prs_commits', 'pr_id'):
            # Drop old constraint and add new one for prs_commits
            drop_constraint_if_exists('prs_commits', 'fk_prs_commits_pull_request_id')
            add_constraint_if_not_exists('prs_commits', 'fk_prs_commits_pr_id', 'FOREIGN KEY (pr_id) REFERENCES prs(id)')
        
        if column_exists('prs_reviews', 'pr_id'):
            # Drop old constraint and add new one for prs_reviews
            drop_constraint_if_exists('prs_reviews', 'fk_prs_reviews_pull_request_id')
            add_constraint_if_not_exists('prs_reviews', 'fk_prs_reviews_pr_id', 'FOREIGN KEY (pr_id) REFERENCES prs(id)')
        
        if column_exists('prs_comments', 'pr_id'):
            # Drop old constraint and add new one for prs_comments
            drop_constraint_if_exists('prs_comments', 'fk_prs_comments_pull_request_id')
            add_constraint_if_not_exists('prs_comments', 'fk_prs_comments_pr_id', 'FOREIGN KEY (pr_id) REFERENCES prs(id)')
        
        print("\n✅ Migration 0003 completed successfully!")
        print("🔧 PR column names have been standardized to use 'pr_id'.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            print("📡 Database connection closed")

if __name__ == "__main__":
    run_migration()
