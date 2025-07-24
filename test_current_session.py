#!/usr/bin/env python3
"""
Test the current session endpoint
"""

import requests

def test_current_session():
    """Test the current session endpoint"""
    
    print("🔐 Testing current session endpoint...")
    
    # Step 1: Login to get a token
    print("1. Logging in...")
    try:
        login_response = requests.post(
            "http://localhost:3001/auth/login",
            json={"email": "admin@pulse.com", "password": "pulse"},
            timeout=10
        )
        
        if login_response.status_code == 200:
            token = login_response.json()["token"]
            print(f"✅ Login successful, token: {token[:50]}...")
        else:
            print(f"❌ Login failed: {login_response.status_code}")
            return
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return
    
    # Step 2: Test current session endpoint
    print("\n2. Testing current session endpoint...")
    try:
        response = requests.get(
            "http://localhost:3001/api/v1/admin/current-session",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            session_info = response.json()
            print(f"✅ Current session info: {session_info}")
        else:
            print(f"❌ Current session endpoint failed")
            
    except Exception as e:
        print(f"❌ Current session error: {e}")
    
    # Step 3: Test active sessions endpoint for comparison
    print("\n3. Testing active sessions endpoint...")
    try:
        response = requests.get(
            "http://localhost:3001/api/v1/admin/active-sessions",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"Active sessions status: {response.status_code}")
        
        if response.status_code == 200:
            sessions = response.json()
            print(f"✅ Active sessions count: {len(sessions)}")
            for session in sessions:
                print(f"   Session ID: {session.get('session_id')}, User: {session.get('email')}")
        else:
            print(f"❌ Active sessions failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Active sessions error: {e}")

if __name__ == "__main__":
    test_current_session()
