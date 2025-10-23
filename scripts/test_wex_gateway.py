#!/usr/bin/env python3
"""
WEX Gateway Validation Test Script
==================================

This script validates the WEX Gateway connection and helps diagnose connection errors.
It tests both embedding and text generation capabilities with detailed error reporting.

Usage:
    python scripts/test_wex_gateway.py [--tenant-id TENANT_ID] [--verbose]

Requirements:
    - Backend service database connection
    - WEX Gateway integration configured in database
    - Valid API credentials
"""

import asyncio
import argparse
import logging
import sys
import time
import json
from typing import Dict, Any, Optional
from pathlib import Path

# Add the backend service to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "backend-service"))

from app.core.database import get_database
from app.models.unified_models import Integration
from app.ai.providers.wex_gateway_provider import WEXGatewayProvider
from app.core.config import AppConfig
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WEXGatewayTester:
    """Test suite for WEX Gateway validation"""
    
    def __init__(self, tenant_id: int = 1, verbose: bool = False):
        self.tenant_id = tenant_id
        self.verbose = verbose
        self.database = get_database()
        self.provider: Optional[WEXGatewayProvider] = None
        
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger('app.ai.providers.wex_gateway_provider').setLevel(logging.DEBUG)
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run comprehensive WEX Gateway validation tests"""
        results = {
            "timestamp": time.time(),
            "tenant_id": self.tenant_id,
            "tests": {}
        }
        
        print("🔍 WEX Gateway Validation Test Suite")
        print("=" * 50)
        
        # Test 1: Database Integration Check
        print("\n1️⃣ Testing Database Integration Configuration...")
        results["tests"]["database_config"] = await self._test_database_config()
        
        # Test 2: Provider Initialization
        print("\n2️⃣ Testing Provider Initialization...")
        results["tests"]["provider_init"] = await self._test_provider_initialization()
        
        if not self.provider:
            print("❌ Cannot continue tests - provider initialization failed")
            return results
        
        # Test 3: Basic Connectivity
        print("\n3️⃣ Testing Basic Connectivity...")
        results["tests"]["connectivity"] = await self._test_basic_connectivity()
        
        # Test 4: Embedding Generation
        print("\n4️⃣ Testing Embedding Generation...")
        results["tests"]["embeddings"] = await self._test_embedding_generation()
        
        # Test 5: Text Generation
        print("\n5️⃣ Testing Text Generation...")
        results["tests"]["text_generation"] = await self._test_text_generation()
        
        # Test 6: Batch Processing
        print("\n6️⃣ Testing Batch Processing...")
        results["tests"]["batch_processing"] = await self._test_batch_processing()
        
        # Test 7: Error Handling
        print("\n7️⃣ Testing Error Handling...")
        results["tests"]["error_handling"] = await self._test_error_handling()
        
        # Summary
        print("\n📊 Test Summary")
        print("=" * 50)
        self._print_summary(results)
        
        return results
    
    async def _test_database_config(self) -> Dict[str, Any]:
        """Test database integration configuration"""
        try:
            with self.database.get_read_session_context() as session:
                # Query WEX Gateway integration
                integration = session.query(Integration).filter(
                    Integration.tenant_id == self.tenant_id,
                    Integration.provider.ilike('%wex%'),
                    Integration.type.in_(['AI', 'Embedding']),
                    Integration.active == True
                ).first()

                if not integration:
                    # Try alternative provider names
                    integration = session.query(Integration).filter(
                        Integration.tenant_id == self.tenant_id,
                        Integration.type.in_(['AI', 'Embedding']),
                        Integration.active == True
                    ).first()
                
                if not integration:
                    return {
                        "status": "failed",
                        "error": f"No active AI provider integration found for tenant {self.tenant_id}",
                        "suggestion": "Check if WEX Gateway integration is configured in the database"
                    }
                
                # Validate configuration
                config_issues = []
                if not integration.base_url:
                    config_issues.append("Missing base_url")
                if not integration.password:
                    config_issues.append("Missing API key (password field)")
                
                settings = integration.settings or {}
                if not settings.get('model_path'):
                    config_issues.append("Missing model_path in settings")
                
                result = {
                    "status": "success" if not config_issues else "warning",
                    "integration_id": integration.id,
                    "provider": integration.provider,
                    "base_url": integration.base_url,
                    "has_api_key": bool(integration.password),
                    "settings": settings,
                    "issues": config_issues
                }
                
                print(f"   ✅ Found integration: {integration.provider} (ID: {integration.id})")
                print(f"   🔗 Base URL: {integration.base_url}")
                print(f"   🔑 API Key: {'✅ Present' if integration.password else '❌ Missing'}")
                print(f"   ⚙️  Settings: {json.dumps(settings, indent=6)}")
                
                if config_issues:
                    print(f"   ⚠️  Issues: {', '.join(config_issues)}")
                
                return result
                
        except Exception as e:
            error_msg = f"Database configuration test failed: {e}"
            print(f"   ❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }
    
    async def _test_provider_initialization(self) -> Dict[str, Any]:
        """Test WEX Gateway provider initialization"""
        try:
            with self.database.get_read_session_context() as session:
                integration = session.query(Integration).filter(
                    Integration.tenant_id == self.tenant_id,
                    Integration.type.in_(['AI', 'Embedding']),
                    Integration.active == True
                ).first()
                
                if not integration:
                    return {
                        "status": "failed",
                        "error": "No integration found for provider initialization"
                    }
                
                # Initialize provider
                self.provider = WEXGatewayProvider(integration)
                
                # Validate provider attributes
                validation_results = {
                    "base_url": self.provider.base_url,
                    "has_api_key": bool(self.provider.api_key),
                    "model_name": self.provider.model_name,
                    "client_initialized": bool(self.provider.client),
                    "timeout": self.provider.model_config.get('timeout', 120)
                }
                
                print(f"   ✅ Provider initialized successfully")
                print(f"   🔗 Base URL: {validation_results['base_url']}")
                print(f"   🤖 Model: {validation_results['model_name']}")
                print(f"   ⏱️  Timeout: {validation_results['timeout']}s")
                
                return {
                    "status": "success",
                    **validation_results
                }
                
        except Exception as e:
            error_msg = f"Provider initialization failed: {e}"
            print(f"   ❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }
    
    async def _test_basic_connectivity(self) -> Dict[str, Any]:
        """Test basic connectivity to WEX Gateway"""
        try:
            start_time = time.time()
            health_result = await self.provider.health_check()
            response_time = time.time() - start_time
            
            print(f"   🏥 Health check: {health_result['status']}")
            print(f"   ⏱️  Response time: {response_time:.2f}s")
            
            if health_result['status'] == 'healthy':
                print(f"   ✅ Gateway is responding correctly")
            else:
                print(f"   ❌ Gateway health check failed: {health_result.get('error', 'Unknown error')}")
            
            return {
                "status": health_result['status'],
                "response_time": response_time,
                "health_result": health_result
            }
            
        except Exception as e:
            error_msg = f"Connectivity test failed: {e}"
            print(f"   ❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }

    async def _test_embedding_generation(self) -> Dict[str, Any]:
        """Test embedding generation with various inputs"""
        test_cases = [
            "Simple test text",
            "This is a longer test text to validate embedding generation with more content",
            "Special characters: !@#$%^&*()_+-=[]{}|;:,.<>?",
            ""  # Empty string test
        ]

        results = []

        for i, text in enumerate(test_cases):
            try:
                start_time = time.time()
                embeddings = await self.provider.generate_embeddings([text])
                response_time = time.time() - start_time

                if embeddings and len(embeddings) > 0:
                    embedding = embeddings[0]
                    result = {
                        "test_case": i + 1,
                        "text": text[:50] + "..." if len(text) > 50 else text,
                        "status": "success",
                        "embedding_length": len(embedding),
                        "response_time": response_time,
                        "non_zero_values": sum(1 for x in embedding if x != 0.0)
                    }
                    print(f"   ✅ Test {i+1}: Generated {len(embedding)}D embedding in {response_time:.2f}s")
                else:
                    result = {
                        "test_case": i + 1,
                        "text": text,
                        "status": "failed",
                        "error": "No embeddings returned"
                    }
                    print(f"   ❌ Test {i+1}: No embeddings returned")

                results.append(result)

            except Exception as e:
                result = {
                    "test_case": i + 1,
                    "text": text,
                    "status": "failed",
                    "error": str(e)
                }
                results.append(result)
                print(f"   ❌ Test {i+1}: {e}")

        success_count = sum(1 for r in results if r["status"] == "success")

        return {
            "status": "success" if success_count > 0 else "failed",
            "success_rate": f"{success_count}/{len(test_cases)}",
            "results": results
        }

    async def _test_text_generation(self) -> Dict[str, Any]:
        """Test text generation capabilities"""
        test_prompts = [
            "Hello, how are you?",
            "Explain what an API is in one sentence.",
            "What is 2 + 2?"
        ]

        results = []

        for i, prompt in enumerate(test_prompts):
            try:
                start_time = time.time()
                response = await self.provider.generate_text(prompt)
                response_time = time.time() - start_time

                if response and len(response.strip()) > 0:
                    result = {
                        "test_case": i + 1,
                        "prompt": prompt,
                        "status": "success",
                        "response_length": len(response),
                        "response_time": response_time,
                        "response_preview": response[:100] + "..." if len(response) > 100 else response
                    }
                    print(f"   ✅ Test {i+1}: Generated {len(response)} chars in {response_time:.2f}s")
                else:
                    result = {
                        "test_case": i + 1,
                        "prompt": prompt,
                        "status": "failed",
                        "error": "Empty response"
                    }
                    print(f"   ❌ Test {i+1}: Empty response")

                results.append(result)

            except Exception as e:
                result = {
                    "test_case": i + 1,
                    "prompt": prompt,
                    "status": "failed",
                    "error": str(e)
                }
                results.append(result)
                print(f"   ❌ Test {i+1}: {e}")

        success_count = sum(1 for r in results if r["status"] == "success")

        return {
            "status": "success" if success_count > 0 else "failed",
            "success_rate": f"{success_count}/{len(test_prompts)}",
            "results": results
        }

    async def _test_batch_processing(self) -> Dict[str, Any]:
        """Test batch processing capabilities"""
        batch_texts = [f"Test text number {i}" for i in range(1, 11)]  # 10 texts

        try:
            start_time = time.time()
            embeddings = await self.provider.generate_embeddings(batch_texts)
            response_time = time.time() - start_time

            if len(embeddings) == len(batch_texts):
                print(f"   ✅ Batch processing: {len(embeddings)} embeddings in {response_time:.2f}s")
                print(f"   📊 Average time per embedding: {response_time/len(embeddings):.3f}s")

                return {
                    "status": "success",
                    "batch_size": len(batch_texts),
                    "embeddings_returned": len(embeddings),
                    "total_time": response_time,
                    "avg_time_per_item": response_time / len(embeddings)
                }
            else:
                error_msg = f"Expected {len(batch_texts)} embeddings, got {len(embeddings)}"
                print(f"   ❌ {error_msg}")
                return {
                    "status": "failed",
                    "error": error_msg
                }

        except Exception as e:
            error_msg = f"Batch processing failed: {e}"
            print(f"   ❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }

    async def _test_error_handling(self) -> Dict[str, Any]:
        """Test error handling with invalid inputs"""
        test_cases = [
            {
                "name": "Very long text",
                "input": "x" * 10000,  # Very long text
                "expected": "should handle gracefully"
            },
            {
                "name": "Empty list",
                "input": [],
                "expected": "should return empty list"
            }
        ]

        results = []

        for test_case in test_cases:
            try:
                if test_case["name"] == "Empty list":
                    embeddings = await self.provider.generate_embeddings(test_case["input"])
                else:
                    embeddings = await self.provider.generate_embeddings([test_case["input"]])

                result = {
                    "test_name": test_case["name"],
                    "status": "success",
                    "result": f"Returned {len(embeddings)} embeddings"
                }
                print(f"   ✅ {test_case['name']}: Handled gracefully")

            except Exception as e:
                result = {
                    "test_name": test_case["name"],
                    "status": "error",
                    "error": str(e)
                }
                print(f"   ⚠️  {test_case['name']}: {e}")

            results.append(result)

        return {
            "status": "completed",
            "results": results
        }

    def _print_summary(self, results: Dict[str, Any]):
        """Print test summary"""
        tests = results["tests"]

        print(f"Tenant ID: {results['tenant_id']}")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(results['timestamp']))}")
        print()

        for test_name, test_result in tests.items():
            status = test_result.get("status", "unknown")
            if status == "success":
                print(f"✅ {test_name.replace('_', ' ').title()}: PASSED")
            elif status == "failed":
                print(f"❌ {test_name.replace('_', ' ').title()}: FAILED")
                if "error" in test_result:
                    print(f"   Error: {test_result['error']}")
            elif status == "warning":
                print(f"⚠️  {test_name.replace('_', ' ').title()}: WARNING")
            else:
                print(f"❓ {test_name.replace('_', ' ').title()}: {status.upper()}")

        # Overall status
        failed_tests = [name for name, result in tests.items() if result.get("status") == "failed"]
        if not failed_tests:
            print(f"\n🎉 All tests completed successfully!")
        else:
            print(f"\n⚠️  {len(failed_tests)} test(s) failed: {', '.join(failed_tests)}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test WEX Gateway connectivity and functionality")
    parser.add_argument("--tenant-id", type=int, default=1, help="Tenant ID to test (default: 1)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", type=str, help="Save results to JSON file")

    args = parser.parse_args()

    tester = WEXGatewayTester(tenant_id=args.tenant_id, verbose=args.verbose)

    try:
        results = await tester.run_all_tests()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to: {args.output}")

        # Exit with error code if any tests failed
        failed_tests = [name for name, result in results["tests"].items() if result.get("status") == "failed"]
        if failed_tests:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
