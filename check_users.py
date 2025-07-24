#!/usr/bin/env python3
"""
Simple script to check users in the database and create a test user if needed.
"""

import sys
from pathlib import Path

# Add the backend service to the path for database access
sys.path.append(str(Path(__file__).parent / "services" / "backend-service"))

def main():
    try:
        # Import database modules
        from app.core.database import get_database
        from app.models.unified_models import User
        from app.core.utils import DateTimeHelper
        import bcrypt
        
        print("🔍 Checking database for users...")
        
        database = get_database()
        with database.get_session() as session:
            # List existing users
            users = session.query(User).filter(User.active == True).all()
            
            if users:
                print(f"✅ Found {len(users)} active users:")
                for user in users:
                    print(f"  - {user.email} (Role: {user.role}, Admin: {user.is_admin})")
            else:
                print("⚠️  No active users found. Creating test user...")
                
                # Create test user
                password = "password123"
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                test_user = User(
                    email="test@wex.com",
                    first_name="Test",
                    last_name="User",
                    role="admin",
                    is_admin=True,
                    password_hash=password_hash,
                    active=True,
                    client_id=1,  # Assuming client_id 1 exists
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                
                session.add(test_user)
                session.commit()
                
                print("✅ Created test user:")
                print("   Email: test@wex.com")
                print("   Password: password123")
                print("   Role: admin")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
