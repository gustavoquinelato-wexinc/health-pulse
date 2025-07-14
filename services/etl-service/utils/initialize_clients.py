#!/usr/bin/env python3
"""
Initialize Clients Table

This script initializes the clients table with a default client.
Run this after creating the new database schema.
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.database import get_database
from app.models.unified_models import Client


def initialize_clients():
    """Initialize the clients table with a default client."""
    print("🔧 Initializing Clients Table")
    print("=" * 60)
    
    settings = get_settings()
    
    try:
        database = get_database()
        with database.get_session() as session:
            # Check if any clients already exist
            existing_clients = session.query(Client).count()
            
            if existing_clients > 0:
                print(f"✅ Clients table already has {existing_clients} client(s)")
                return
            
            # Create default client
            default_client = Client(
                name="WEX Health",
                website="https://www.wexhealth.com",
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )
            
            session.add(default_client)
            session.commit()
            
            print("✅ Successfully created default client:")
            print(f"   ID: {default_client.id}")
            print(f"   Name: {default_client.name}")
            print(f"   Website: {default_client.website}")
            print(f"   Active: {default_client.active}")
            
    except Exception as e:
        print(f"❌ Error initializing clients: {e}")
        raise


if __name__ == "__main__":
    initialize_clients()
