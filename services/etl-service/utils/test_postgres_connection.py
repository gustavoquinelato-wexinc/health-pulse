#!/usr/bin/env python3
"""
Test PostgreSQL connection using the new configuration.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.database import get_database

def test_direct_connection():
    """Test direct psycopg2 connection."""
    print("🔍 Testing Direct PostgreSQL Connection...")
    
    try:
        import psycopg2
        
        settings = get_settings()
        
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DATABASE,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )

        cur = conn.cursor()
        cur.execute("SELECT version();")
        db_version = cur.fetchone()
        print(f"✅ Connected to PostgreSQL: {db_version[0]}")

        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Direct connection failed: {e}")
        return False

def test_sqlalchemy_connection():
    """Test SQLAlchemy connection through our database class."""
    print("\n🔍 Testing SQLAlchemy Connection...")
    
    try:
        database = get_database()
        
        if database.is_connection_alive():
            print("✅ SQLAlchemy connection is alive")
            
            # Test a simple query
            with database.get_session_context() as session:
                from sqlalchemy import text
                result = session.execute(text("SELECT current_database(), current_user"))
                db_info = result.fetchone()
                print(f"✅ Connected to database: {db_info[0]} as user: {db_info[1]}")
            
            return True
        else:
            print("❌ SQLAlchemy connection is not alive")
            return False
            
    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 PostgreSQL Connection Test")
    print("=" * 50)
    
    # Test direct connection
    direct_ok = test_direct_connection()
    
    # Test SQLAlchemy connection
    sqlalchemy_ok = test_sqlalchemy_connection()
    
    print("\n📊 Test Results:")
    print("=" * 50)
    print(f"Direct Connection: {'✅ PASS' if direct_ok else '❌ FAIL'}")
    print(f"SQLAlchemy Connection: {'✅ PASS' if sqlalchemy_ok else '❌ FAIL'}")
    
    if direct_ok and sqlalchemy_ok:
        print("\n🎉 All tests passed! PostgreSQL migration is ready.")
        return 0
    else:
        print("\n💥 Some tests failed. Check your configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
