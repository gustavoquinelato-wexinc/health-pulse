#!/usr/bin/env python3
"""
Simple test to check if backend service is running
"""

import asyncio
import httpx

async def test_backend_health():
    """Test if backend service is running"""
    print("🔍 Checking if backend service is running...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to connect to backend service
            response = await client.get("http://localhost:3001/")
            print(f"✅ Backend service is running! Status: {response.status_code}")
            return True
            
    except httpx.ConnectError:
        print("❌ Backend service is not running (connection refused)")
        return False
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_backend_health())
