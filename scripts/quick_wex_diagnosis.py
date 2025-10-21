#!/usr/bin/env python3
"""
Quick WEX Gateway Diagnosis Script
=================================

Fast diagnostic script to quickly identify common WEX Gateway connection issues.
This script performs essential checks and provides immediate feedback.

Usage:
    python scripts/quick_wex_diagnosis.py [--tenant-id TENANT_ID]
"""

import sys
import json
import time
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

# Add the backend service to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "backend-service"))

try:
    from app.core.database import get_database
    from app.models.unified_models import Integration
    from app.core.config import AppConfig
    import asyncio
    import aiohttp
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root and backend service dependencies are installed.")
    sys.exit(1)

def print_header():
    """Print diagnostic header"""
    print("🔍 WEX Gateway Quick Diagnosis")
    print("=" * 40)
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_database_connection():
    """Check if database connection works"""
    print("1️⃣ Database Connection...")
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Simple query to test connection
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).fetchone()
            if result:
                print("   ✅ Database connection: OK")
                return True
            else:
                print("   ❌ Database connection: Failed to execute test query")
                return False
    except Exception as e:
        print(f"   ❌ Database connection: {e}")
        return False

def check_integration_config(tenant_id: int = 1):
    """Check WEX Gateway integration configuration"""
    print(f"2️⃣ Integration Configuration (Tenant {tenant_id})...")
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Look for WEX Gateway or any AI/Embedding integration
            integration = session.query(Integration).filter(
                Integration.tenant_id == tenant_id,
                Integration.type.in_(['AI', 'Embedding']),
                Integration.active == True
            ).first()
            
            if not integration:
                print(f"   ❌ No active AI/Embedding integration found for tenant {tenant_id}")
                print("   💡 Suggestion: Run migration script to create WEX Gateway integration")
                return None
            
            print(f"   ✅ Found integration: {integration.provider} (ID: {integration.id})")
            
            # Check critical fields
            issues = []
            if not integration.base_url:
                issues.append("Missing base_url")
            if not integration.password:
                issues.append("Missing API key")
            
            settings = integration.settings or {}
            if not settings.get('model_path'):
                issues.append("Missing model_path in settings")
            
            if issues:
                print(f"   ⚠️  Configuration issues: {', '.join(issues)}")
            else:
                print("   ✅ Configuration: Complete")
            
            # Show key details (without sensitive data)
            print(f"   🔗 Base URL: {integration.base_url}")
            print(f"   🔑 API Key: {'Present' if integration.password else 'Missing'}")
            print(f"   🤖 Model: {settings.get('model_path', 'Not configured')}")
            
            return integration
            
    except Exception as e:
        print(f"   ❌ Integration check failed: {e}")
        return None

def check_encryption_key():
    """Check if encryption key is available"""
    print("3️⃣ Encryption Key...")
    try:
        key = AppConfig.load_key()
        if key:
            print("   ✅ Encryption key: Available")
            return True
        else:
            print("   ❌ Encryption key: Not found")
            print("   💡 Suggestion: Set ENCRYPTION_KEY environment variable")
            return False
    except Exception as e:
        print(f"   ❌ Encryption key check failed: {e}")
        return False

async def check_network_connectivity(base_url: str, api_key: str = None):
    """Check basic network connectivity to WEX Gateway"""
    print("4️⃣ Network Connectivity...")
    
    if not base_url:
        print("   ❌ No base URL to test")
        return False
    
    try:
        # Test basic connectivity (without authentication)
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Try to reach the base URL
            try:
                async with session.get(base_url) as response:
                    print(f"   ✅ Base URL reachable: {response.status}")
                    
                    # If we have an API key, try a simple authenticated request
                    if api_key:
                        headers = {"Authorization": f"Bearer {api_key}"}
                        # Try common health/status endpoints
                        test_endpoints = ["/health", "/status", "/v1/models"]
                        
                        for endpoint in test_endpoints:
                            try:
                                test_url = base_url.rstrip('/') + endpoint
                                async with session.get(test_url, headers=headers) as auth_response:
                                    if auth_response.status < 500:  # Any non-server-error response
                                        print(f"   ✅ Authenticated request: {auth_response.status} ({endpoint})")
                                        return True
                            except:
                                continue
                        
                        print("   ⚠️  Authenticated requests: No successful endpoint found")
                    
                    return True
                    
            except aiohttp.ClientConnectorError as e:
                print(f"   ❌ Connection failed: {e}")
                print("   💡 Check if URL is correct and service is running")
                return False
            except asyncio.TimeoutError:
                print("   ❌ Connection timeout")
                print("   💡 Check network connectivity and firewall settings")
                return False
                
    except Exception as e:
        print(f"   ❌ Network test failed: {e}")
        return False

def check_environment_variables():
    """Check relevant environment variables"""
    print("5️⃣ Environment Variables...")
    
    import os
    
    env_vars = {
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST'),
        'POSTGRES_DATABASE': os.getenv('POSTGRES_DATABASE'),
        'ENCRYPTION_KEY': '***' if os.getenv('ENCRYPTION_KEY') else None,
    }

    # WEX Gateway variables are optional (stored in database)
    optional_vars = {
        'WEX_AI_GATEWAY_BASE_URL': os.getenv('WEX_AI_GATEWAY_BASE_URL'),
        'WEX_AI_GATEWAY_API_KEY': '***' if os.getenv('WEX_AI_GATEWAY_API_KEY') else None,
    }
    
    missing = []
    for var, value in env_vars.items():
        if value:
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ❌ {var}: Not set")
            missing.append(var)

    # Check optional variables
    print("   📋 Optional variables (WEX Gateway can be configured in database):")
    for var, value in optional_vars.items():
        if value:
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ⚪ {var}: Not set (OK if configured in database)")

    if missing:
        print(f"   💡 Missing required variables: {', '.join(missing)}")
        return False
    else:
        print("   ✅ All required environment variables are set")
        return True

async def main():
    """Main diagnostic function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quick WEX Gateway diagnosis")
    parser.add_argument("--tenant-id", type=int, default=1, help="Tenant ID to check (default: 1)")
    args = parser.parse_args()
    
    print_header()
    
    # Track results
    results = {
        'database': False,
        'integration': False,
        'encryption': False,
        'network': False,
        'environment': False
    }
    
    # 1. Database connection
    results['database'] = check_database_connection()
    print()
    
    # 2. Integration configuration
    integration = None
    if results['database']:
        integration = check_integration_config(args.tenant_id)
        results['integration'] = integration is not None
    else:
        print("2️⃣ Integration Configuration... ⏭️  Skipped (database connection failed)")
    print()
    
    # 3. Encryption key
    results['encryption'] = check_encryption_key()
    print()
    
    # 4. Network connectivity
    if integration and integration.base_url:
        api_key = None
        if integration.password and results['encryption']:
            try:
                api_key = AppConfig.decrypt_token(integration.password, AppConfig.load_key())
            except:
                pass
        
        results['network'] = await check_network_connectivity(integration.base_url, api_key)
    else:
        print("4️⃣ Network Connectivity... ⏭️  Skipped (no integration or base URL)")
    print()
    
    # 5. Environment variables
    results['environment'] = check_environment_variables()
    print()
    
    # Summary
    print("📊 Diagnosis Summary")
    print("=" * 40)
    
    passed = sum(results.values())
    total = len(results)
    
    for check, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {check.replace('_', ' ').title()}")
    
    print()
    if passed == total:
        print("🎉 All checks passed! WEX Gateway should be working.")
        print("💡 If you're still seeing errors, run the full test suite:")
        print("   python scripts/test_wex_gateway.py --verbose")
    else:
        print(f"⚠️  {total - passed} issue(s) found. Address the failed checks above.")
        print()
        print("🔧 Next Steps:")
        if not results['database']:
            print("   • Fix database connection issues first")
        if not results['integration']:
            print("   • Run migration script: python services/backend-service/scripts/migrations/0002_initial_seed_data_wex.py")
        if not results['encryption']:
            print("   • Set ENCRYPTION_KEY environment variable")
        if not results['network']:
            print("   • Check network connectivity and WEX Gateway service status")
        if not results['environment']:
            print("   • Set missing environment variables")
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    asyncio.run(main())
