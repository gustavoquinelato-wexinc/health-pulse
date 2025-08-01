#!/usr/bin/env python3
"""
Test script to verify CLIENT_NAME lookup functionality.

This script tests:
1. Case-insensitive client name lookup
2. Error handling for invalid client names
3. Database client ID resolution
"""

import sys
import os

# Add the services directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'etl-service'))

def test_client_name_lookup():
    """Test client name lookup functionality."""
    
    print("🧪 Testing CLIENT_NAME Lookup")
    print("=" * 40)
    
    try:
        # Import after path setup
        from app.core.config import get_client_id_from_name
        from app.core.database import get_database
        from app.models.unified_models import Client
        
        database = get_database()
        
        # Step 1: Show available clients
        print("\n📋 Step 1: Available Clients in Database")
        with database.get_session() as session:
            clients = session.query(Client).all()
            
            for client in clients:
                status = "ACTIVE" if client.active else "INACTIVE"
                print(f"  • {client.name} (ID: {client.id}): {status}")
        
        # Step 2: Test case-insensitive lookup
        print("\n📋 Step 2: Testing Case-Insensitive Lookup")
        
        test_cases = [
            "WEX",        # Exact match
            "wex",        # Lowercase
            "Wex",        # Mixed case
            "WEX ",       # With trailing space
            " WEX",       # With leading space
            "TechCorp",   # Exact match
            "techcorp",   # Lowercase
            "TECHCORP",   # Uppercase
        ]
        
        for test_name in test_cases:
            try:
                client_id = get_client_id_from_name(test_name)
                print(f"  ✅ '{test_name}' → Client ID: {client_id}")
            except Exception as e:
                print(f"  ❌ '{test_name}' → Error: {e}")
        
        # Step 3: Test invalid client names
        print("\n📋 Step 3: Testing Invalid Client Names")
        
        invalid_cases = [
            "NonExistent",
            "InvalidClient",
            "",
            "   ",
        ]
        
        for test_name in invalid_cases:
            try:
                client_id = get_client_id_from_name(test_name)
                print(f"  ⚠️ '{test_name}' → Unexpected success: {client_id}")
            except Exception as e:
                print(f"  ✅ '{test_name}' → Expected error: {str(e)[:80]}...")
        
        print("\n✅ CLIENT_NAME Lookup Test Complete!")
        print("\n🎯 Expected Results:")
        print("  • Case-insensitive matching works (WEX = wex = Wex)")
        print("  • Whitespace is handled properly")
        print("  • Invalid names show helpful error messages")
        print("  • Error messages list available clients")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_client_name_lookup()
