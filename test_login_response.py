#!/usr/bin/env python3
"""
Test script to check the login response structure
"""

import requests
import json

def test_login():
    """Test login and check response structure"""
    print("Testing login response structure...")
    
    try:
        response = requests.post(
            "http://localhost:3001/auth/login",
            json={
                "email": "admin@pulse.com",
                "password": "pulse"
            },
            timeout=10.0
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Data: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
