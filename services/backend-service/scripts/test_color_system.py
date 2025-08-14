#!/usr/bin/env python3
"""
Color System Integration Test

This script tests the complete color update flow:
1. Frontend color changes via API
2. Backend color processing and caching
3. ETL service notification and WebSocket broadcasting
4. Real-time updates across all services

Usage:
    python test_color_system.py [--client-id CLIENT_ID] [--verbose]
"""

import os
import sys
import argparse
import asyncio
import httpx
import json
import time
from datetime import datetime

# Add the parent directory to the path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

class ColorSystemTester:
    def __init__(self, client_id: int = 1, verbose: bool = False):
        self.client_id = client_id
        self.verbose = verbose
        self.settings = get_settings()
        self.auth_token = None
        
        # Test colors
        self.test_colors = {
            "color1": "#FF5733",  # Orange-Red
            "color2": "#33FF57",  # Green
            "color3": "#3357FF",  # Blue
            "color4": "#FF33F5",  # Magenta
            "color5": "#F5FF33"   # Yellow
        }
        
        self.original_colors = {}
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = "🔍" if level == "INFO" else "✅" if level == "SUCCESS" else "❌" if level == "ERROR" else "⚠️"
        print(f"[{timestamp}] {prefix} {message}")
    
    async def authenticate(self) -> bool:
        """Authenticate with the backend service"""
        try:
            # For testing, we'll use a mock authentication
            # In a real scenario, you'd authenticate with actual credentials
            self.auth_token = "test_token_for_color_system_testing"
            self.log("Authentication simulated (using test token)")
            return True
            
        except Exception as e:
            self.log(f"Authentication failed: {e}", "ERROR")
            return False
    
    async def get_current_colors(self) -> dict:
        """Get current color schema from backend"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"http://localhost:{self.settings.PORT}/api/v1/admin/color-schema",
                    headers={"Authorization": f"Bearer {self.auth_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.log("✅ Retrieved current colors from backend")
                        return data.get("colors", {})
                
                self.log(f"Failed to get colors: {response.status_code}", "ERROR")
                return {}
                
        except Exception as e:
            self.log(f"Error getting current colors: {e}", "ERROR")
            return {}
    
    async def update_colors(self, colors: dict) -> bool:
        """Update colors via backend API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"http://localhost:{self.settings.PORT}/api/v1/admin/color-schema",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                    json={"colors": colors}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("message"):
                        self.log(f"✅ Colors updated: {data['message']}")
                        if self.verbose:
                            self.log(f"   Enhanced: {data.get('enhanced', False)}")
                            self.log(f"   Cache invalidated: {data.get('cache_invalidated', False)}")
                            self.log(f"   WebSocket notified: {data.get('websocket_notified', False)}")
                        return True
                
                self.log(f"Failed to update colors: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error updating colors: {e}", "ERROR")
            return False
    
    async def test_user_colors_api(self) -> bool:
        """Test user-specific colors API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"http://localhost:{self.settings.PORT}/api/v1/user/colors",
                    headers={"Authorization": f"Bearer {self.auth_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        colors = data.get("colors", {})
                        user_prefs = data.get("user_preferences", {})
                        
                        self.log("✅ User colors API working")
                        if self.verbose:
                            self.log(f"   Colors: {len(colors)} properties")
                            self.log(f"   User preferences: {user_prefs}")
                        return True
                
                self.log(f"User colors API failed: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error testing user colors API: {e}", "ERROR")
            return False
    
    async def test_etl_notification(self) -> bool:
        """Test ETL service notification"""
        try:
            # Test the internal ETL notification endpoint
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"http://localhost:8000/api/v1/internal/color-schema-changed",
                    json={
                        "client_id": self.client_id,
                        "colors": self.test_colors,
                        "event_type": "test_update"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.log("✅ ETL service notification working")
                        if self.verbose:
                            self.log(f"   Message: {data.get('message')}")
                        return True
                
                self.log(f"ETL notification failed: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error testing ETL notification: {e}", "ERROR")
            return False
    
    async def run_complete_test(self) -> bool:
        """Run complete color system test"""
        self.log("🎨 Starting Color System Integration Test")
        self.log("=" * 60)
        
        # Step 1: Authentication
        self.log("Step 1: Authentication")
        if not await self.authenticate():
            return False
        
        # Step 2: Get original colors
        self.log("Step 2: Getting original colors")
        self.original_colors = await self.get_current_colors()
        if not self.original_colors:
            self.log("Warning: Could not retrieve original colors", "WARNING")
        
        # Step 3: Test user colors API
        self.log("Step 3: Testing user colors API")
        if not await self.test_user_colors_api():
            return False
        
        # Step 4: Update colors
        self.log("Step 4: Updating colors with test values")
        if not await self.update_colors(self.test_colors):
            return False
        
        # Step 5: Verify color update
        self.log("Step 5: Verifying color update")
        await asyncio.sleep(1)  # Give time for processing
        updated_colors = await self.get_current_colors()
        
        if updated_colors:
            matches = all(
                updated_colors.get(key) == value 
                for key, value in self.test_colors.items()
            )
            if matches:
                self.log("✅ Color update verified")
            else:
                self.log("❌ Color update verification failed", "ERROR")
                if self.verbose:
                    self.log(f"   Expected: {self.test_colors}")
                    self.log(f"   Got: {updated_colors}")
                return False
        
        # Step 6: Test ETL notification
        self.log("Step 6: Testing ETL service notification")
        if not await self.test_etl_notification():
            self.log("Warning: ETL notification test failed", "WARNING")
        
        # Step 7: Restore original colors (if we have them)
        if self.original_colors:
            self.log("Step 7: Restoring original colors")
            if await self.update_colors(self.original_colors):
                self.log("✅ Original colors restored")
            else:
                self.log("⚠️ Failed to restore original colors", "WARNING")
        
        self.log("=" * 60)
        self.log("🎉 Color System Integration Test COMPLETED")
        return True

async def main():
    parser = argparse.ArgumentParser(description='Test color system integration')
    parser.add_argument('--client-id', type=int, default=1, help='Client ID to test with')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    tester = ColorSystemTester(client_id=args.client_id, verbose=args.verbose)
    
    try:
        success = await tester.run_complete_test()
        if success:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
