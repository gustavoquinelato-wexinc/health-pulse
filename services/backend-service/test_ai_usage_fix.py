#!/usr/bin/env python3
"""
Test script to verify AI usage tracking fix.
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_ai_usage_tracking():
    """Test AI usage tracking without errors."""
    print("🧪 Testing AI Usage Tracking Fix...")
    
    try:
        from app.core.database import get_database
        from app.ai.hybrid_provider_manager import HybridProviderManager
        from app.models.unified_models import AIUsageTracking
        
        # Get database session
        database = get_database()
        
        with database.get_write_session_context() as session:
            # Initialize hybrid manager
            hybrid_manager = HybridProviderManager(session)
            
            # Test usage tracking
            print("📊 Testing usage tracking...")
            
            try:
                # Create a test usage record
                usage_record = AIUsageTracking(
                    tenant_id=1,
                    provider="test_provider",
                    operation="test_operation",
                    input_count=10,
                    cost=0.05,
                    request_metadata={"processing_time": 1.5, "test": True}
                )
                
                session.add(usage_record)
                session.commit()
                
                print("✅ SUCCESS: Usage tracking record created without errors!")
                print(f"   - Record ID: {usage_record.id}")
                print(f"   - Tenant: {usage_record.tenant_id}")
                print(f"   - Provider: {usage_record.provider}")
                print(f"   - Operation: {usage_record.operation}")
                print(f"   - Metadata: {usage_record.request_metadata}")
                
                # Clean up test record
                session.delete(usage_record)
                session.commit()
                print("🧹 Test record cleaned up")
                
                return True
                
            except Exception as e:
                print(f"❌ FAILED: Usage tracking error: {e}")
                return False
                
    except Exception as e:
        print(f"❌ FAILED: Setup error: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 Starting AI Usage Tracking Fix Test")
    print("=" * 50)
    
    success = await test_ai_usage_tracking()
    
    print("=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED! AI usage tracking fix is working.")
    else:
        print("💥 TESTS FAILED! There are still issues with AI usage tracking.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
