#!/usr/bin/env python3
"""
Test script to verify system token creation for ETL jobs
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'etl-service'))

from app.jobs.orchestrator import _get_system_token

def test_system_token():
    """Test system token creation for tenant 1 (WEX)"""
    print("Testing system token creation for tenant 1 (WEX)...")
    
    token = _get_system_token(1)
    
    if token:
        print(f"✅ System token created successfully: {token[:50]}...")
        return True
    else:
        print("❌ Failed to create system token")
        return False

if __name__ == "__main__":
    success = test_system_token()
    sys.exit(0 if success else 1)
