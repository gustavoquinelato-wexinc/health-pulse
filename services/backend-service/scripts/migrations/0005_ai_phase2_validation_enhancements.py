#!/usr/bin/env python3
"""
AI Phase 2: Validation Layer Enhancements
Adds validation-specific columns and indexes to ai_learning_memory table
"""

import os
import sys
import psycopg2
from datetime import datetime

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        connection = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DATABASE', 'pulse_db'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'pulse')
        )
        return connection
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def run_migration():
    """Run the AI Phase 2 validation enhancements migration"""
    print("🚀 Starting AI Phase 2 Validation Enhancements Migration...")
    print("=" * 60)
    
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        print("📋 Adding validation-specific columns to ai_learning_memory...")
        
        # Add validation-specific columns
        validation_columns = [
            "ADD COLUMN IF NOT EXISTS validation_type VARCHAR(50) DEFAULT 'syntax'",
            "ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(3,2) DEFAULT 0.0",
            "ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0",
            "ADD COLUMN IF NOT EXISTS learning_context JSONB DEFAULT '{}'",
            "ADD COLUMN IF NOT EXISTS pattern_hash VARCHAR(64)",
            "ADD COLUMN IF NOT EXISTS resolution_time_ms INTEGER",
            "ADD COLUMN IF NOT EXISTS validation_passed BOOLEAN DEFAULT FALSE"
        ]
        
        for column_def in validation_columns:
            try:
                cursor.execute(f"ALTER TABLE ai_learning_memory {column_def};")
                print(f"   ✅ Added column: {column_def.split('ADD COLUMN IF NOT EXISTS ')[1].split(' ')[0]}")
            except Exception as e:
                print(f"   ⚠️  Column may already exist: {e}")
        
        print("\n📋 Creating validation-specific indexes...")
        
        # Add indexes for validation queries
        validation_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_validation_type ON ai_learning_memory(validation_type);",
            "CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_confidence ON ai_learning_memory(confidence_score);",
            "CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_pattern_hash ON ai_learning_memory(pattern_hash);",
            "CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_validation_passed ON ai_learning_memory(validation_passed);",
            "CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_retry_count ON ai_learning_memory(retry_count);",
            "CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_learning_context ON ai_learning_memory USING GIN(learning_context);"
        ]
        
        for index_sql in validation_indexes:
            try:
                cursor.execute(index_sql)
                index_name = index_sql.split("CREATE INDEX IF NOT EXISTS ")[1].split(" ON")[0]
                print(f"   ✅ Created index: {index_name}")
            except Exception as e:
                print(f"   ⚠️  Index creation issue: {e}")
        
        print("\n📋 Creating validation failure patterns table...")
        
        # Create validation failure patterns table for pattern recognition
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_validation_patterns (
                id SERIAL PRIMARY KEY,
                pattern_hash VARCHAR(64) UNIQUE NOT NULL,
                error_pattern TEXT NOT NULL,
                failure_count INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                last_seen_at TIMESTAMP DEFAULT NOW(),
                pattern_metadata JSONB DEFAULT '{}',
                suggested_fix TEXT,
                confidence_score DECIMAL(3,2) DEFAULT 0.0,
                client_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );
        """)
        print("   ✅ Created ai_validation_patterns table")
        
        # Add indexes for validation patterns
        pattern_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_ai_validation_patterns_hash ON ai_validation_patterns(pattern_hash);",
            "CREATE INDEX IF NOT EXISTS idx_ai_validation_patterns_client ON ai_validation_patterns(client_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_validation_patterns_confidence ON ai_validation_patterns(confidence_score);",
            "CREATE INDEX IF NOT EXISTS idx_ai_validation_patterns_metadata ON ai_validation_patterns USING GIN(pattern_metadata);"
        ]
        
        for index_sql in pattern_indexes:
            cursor.execute(index_sql)
            index_name = index_sql.split("CREATE INDEX IF NOT EXISTS ")[1].split(" ON")[0]
            print(f"   ✅ Created index: {index_name}")
        
        print("\n📋 Recording migration in migration_history...")
        
        # Record migration
        cursor.execute("""
            INSERT INTO migration_history (migration_name, executed_at, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (migration_name) DO UPDATE SET
                executed_at = EXCLUDED.executed_at,
                description = EXCLUDED.description;
        """, (
            '0005_ai_phase2_validation_enhancements',
            datetime.now(),
            'AI Phase 2: Added validation columns, indexes, and patterns table for self-healing validation system'
        ))
        
        connection.commit()
        print("   ✅ Migration recorded successfully")
        
        print("\n" + "=" * 60)
        print("🎉 AI Phase 2 Validation Enhancements Migration completed successfully!")
        print("\n📊 Summary:")
        print("   ✅ Enhanced ai_learning_memory with validation columns")
        print("   ✅ Added validation-specific indexes")
        print("   ✅ Created ai_validation_patterns table")
        print("   ✅ Added pattern recognition indexes")
        print("   ✅ Migration recorded in history")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        connection.rollback()
        return False
        
    finally:
        cursor.close()
        connection.close()

def rollback_migration():
    """Rollback the AI Phase 2 validation enhancements migration"""
    print("🔄 Rolling back AI Phase 2 Validation Enhancements Migration...")
    
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        print("📋 Dropping validation patterns table...")
        cursor.execute("DROP TABLE IF EXISTS ai_validation_patterns CASCADE;")
        
        print("📋 Removing validation columns from ai_learning_memory...")
        validation_columns = [
            "validation_type", "confidence_score", "retry_count", 
            "learning_context", "pattern_hash", "resolution_time_ms", "validation_passed"
        ]
        
        for column in validation_columns:
            try:
                cursor.execute(f"ALTER TABLE ai_learning_memory DROP COLUMN IF EXISTS {column};")
                print(f"   ✅ Removed column: {column}")
            except Exception as e:
                print(f"   ⚠️  Column removal issue: {e}")
        
        print("📋 Removing migration record...")
        cursor.execute("DELETE FROM migration_history WHERE migration_name = %s;", 
                      ('0005_ai_phase2_validation_enhancements',))
        
        connection.commit()
        print("🎉 Rollback completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        connection.rollback()
        return False
        
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback_migration()
    else:
        success = run_migration()
    
    sys.exit(0 if success else 1)
