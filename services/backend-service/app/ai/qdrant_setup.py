"""
Qdrant collection setup and initialization.
Creates all required collections at startup to avoid race conditions.
"""

import asyncio
from typing import List, Dict
from app.core.logging_config import get_logger
from app.ai.qdrant_client import PulseQdrantClient
from app.core.database import get_database
from app.models.unified_models import Tenant

logger = get_logger(__name__)


# Define all collection types that need to be created
# These match the table names that are vectorized by the vectorization worker
COLLECTION_TYPES = [
    'work_items',
    'changelogs',
    'projects',
    'statuses',
    'wits',
    'prs',
    'prs_comments',
    'prs_reviews',
    'prs_commits',
    'repositories',
    'work_items_prs_links',
    'wits_hierarchies',
    'wits_mappings',
    'statuses_mappings',
    'workflows',
    'sprints',
    # Portfolio management collections (not yet implemented in ETL)
    'programs',
    'portfolios',
    'risks',
    'dependencies'
    # Note: custom_fields_mapping is NOT vectorized (it's a configuration table, not content)
]


async def initialize_qdrant_collections() -> Dict[str, any]:
    """
    Initialize all Qdrant collections for all active tenants at startup.
    This prevents race conditions when multiple workers try to create collections simultaneously.
    
    Similar to how RabbitMQ queues are created at startup.
    
    Returns:
        Dict with success status and details
    """
    logger.info("🔧 Initializing Qdrant collections...")
    
    try:
        # Initialize Qdrant client
        qdrant_client = PulseQdrantClient()
        connected = await qdrant_client.initialize()
        
        if not connected:
            logger.error("Failed to connect to Qdrant - skipping collection initialization")
            return {
                "success": False,
                "error": "Failed to connect to Qdrant",
                "collections_created": 0
            }
        
        # Get only tenant 1 for startup initialization
        # Other tenants (2, 3, etc.) should create collections manually via UI
        database = get_database()
        active_tenants: List[Tenant] = []

        with database.get_read_session_context() as session:
            # Only get tenant 1
            tenant_1 = session.query(Tenant).filter(Tenant.id == 1, Tenant.active == True).first()
            if tenant_1:
                active_tenants = [tenant_1]

        if not active_tenants:
            logger.warning("Tenant 1 not found or not active - no collections to create on startup")
            return {
                "success": True,
                "collections_created": 0,
                "message": "Tenant 1 not found or not active"
            }

        logger.info(f"Creating collections for tenant 1 only (other tenants must create manually)")
        
        # Create collections for each tenant
        collections_created = 0
        collections_already_exist = 0
        collections_failed = 0
        
        for tenant in active_tenants:
            tenant_id = tenant.id
            
            for collection_type in COLLECTION_TYPES:
                collection_name = f"tenant_{tenant_id}_{collection_type}"
                
                try:
                    # Use ensure_collection_exists which handles "already exists" gracefully
                    result = await qdrant_client.ensure_collection_exists(
                        collection_name=collection_name,
                        vector_size=1536,  # Standard embedding size
                        distance_metric="Cosine"
                    )
                    
                    if result.success:
                        if result.error and "already exists" in result.error:
                            collections_already_exist += 1
                            logger.debug(f"Collection {collection_name} already exists")
                        else:
                            collections_created += 1
                            logger.info(f"✅ Created collection: {collection_name}")
                    else:
                        collections_failed += 1
                        logger.error(f"Failed to create collection {collection_name}: {result.error}")
                        
                except Exception as e:
                    collections_failed += 1
                    logger.error(f"Error creating collection {collection_name}: {e}")
        
        total_expected = len(active_tenants) * len(COLLECTION_TYPES)
        
        logger.info(
            f"✅ Qdrant collection initialization complete:\n"
            f"   - Created: {collections_created}\n"
            f"   - Already existed: {collections_already_exist}\n"
            f"   - Failed: {collections_failed}\n"
            f"   - Total expected: {total_expected}"
        )
        
        return {
            "success": True,
            "collections_created": collections_created,
            "collections_already_exist": collections_already_exist,
            "collections_failed": collections_failed,
            "total_expected": total_expected,
            "tenants_processed": len(active_tenants)
        }
        
    except Exception as e:
        logger.error(f"❌ Error initializing Qdrant collections: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "collections_created": 0
        }


async def create_all_tenant_collections() -> Dict[str, any]:
    """
    Create all collections for ALL active tenants.
    This is used for manual initialization via the UI.

    Returns:
        Dict with success status and details
    """
    logger.info("🔧 Creating Qdrant collections for ALL active tenants...")

    try:
        # Initialize Qdrant client
        qdrant_client = PulseQdrantClient()
        connected = await qdrant_client.initialize()

        if not connected:
            logger.error("Failed to connect to Qdrant")
            return {
                "success": False,
                "error": "Failed to connect to Qdrant",
                "collections_created": 0
            }

        # Get all active tenants
        database = get_database()
        active_tenants: List[Tenant] = []

        with database.get_read_session_context() as session:
            active_tenants = session.query(Tenant).filter(Tenant.active == True).all()
            tenant_ids = [tenant.id for tenant in active_tenants]

        if not active_tenants:
            logger.warning("No active tenants found")
            return {
                "success": True,
                "collections_created": 0,
                "message": "No active tenants"
            }

        logger.info(f"Found {len(active_tenants)} active tenants: {tenant_ids}")

        # Create collections for each tenant
        collections_created = 0
        collections_already_exist = 0
        collections_failed = 0

        for tenant in active_tenants:
            tenant_id = tenant.id

            for collection_type in COLLECTION_TYPES:
                collection_name = f"tenant_{tenant_id}_{collection_type}"

                try:
                    result = await qdrant_client.ensure_collection_exists(
                        collection_name=collection_name,
                        vector_size=1536,
                        distance_metric="Cosine"
                    )

                    if result.success:
                        if result.error and "already exists" in result.error:
                            collections_already_exist += 1
                            logger.debug(f"Collection {collection_name} already exists")
                        else:
                            collections_created += 1
                            logger.info(f"✅ Created collection: {collection_name}")
                    else:
                        collections_failed += 1
                        logger.error(f"Failed to create collection {collection_name}: {result.error}")

                except Exception as e:
                    collections_failed += 1
                    logger.error(f"Error creating collection {collection_name}: {e}")

        total_expected = len(active_tenants) * len(COLLECTION_TYPES)

        logger.info(
            f"✅ Manual collection creation complete:\n"
            f"   - Created: {collections_created}\n"
            f"   - Already existed: {collections_already_exist}\n"
            f"   - Failed: {collections_failed}\n"
            f"   - Total expected: {total_expected}"
        )

        return {
            "success": True,
            "collections_created": collections_created,
            "collections_already_exist": collections_already_exist,
            "collections_failed": collections_failed,
            "total_expected": total_expected,
            "tenants_processed": len(active_tenants)
        }

    except Exception as e:
        logger.error(f"❌ Error creating collections for all tenants: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "collections_created": 0
        }


async def create_tenant_collections(tenant_id: int) -> Dict[str, any]:
    """
    Create all collections for a specific tenant.
    Useful when a new tenant is added.

    Args:
        tenant_id: Tenant ID to create collections for

    Returns:
        Dict with success status and details
    """
    logger.info(f"Creating Qdrant collections for tenant {tenant_id}...")

    try:
        # Initialize Qdrant client
        qdrant_client = PulseQdrantClient()
        connected = await qdrant_client.initialize()

        if not connected:
            return {
                "success": False,
                "error": "Failed to connect to Qdrant"
            }

        collections_created = 0
        collections_already_exist = 0
        collections_failed = 0

        for collection_type in COLLECTION_TYPES:
            collection_name = f"tenant_{tenant_id}_{collection_type}"

            try:
                result = await qdrant_client.ensure_collection_exists(
                    collection_name=collection_name,
                    vector_size=1536,
                    distance_metric="Cosine"
                )

                if result.success:
                    if result.error and "already exists" in result.error:
                        collections_already_exist += 1
                        logger.debug(f"Collection {collection_name} already exists")
                    else:
                        collections_created += 1
                        logger.info(f"✅ Created collection: {collection_name}")
                else:
                    collections_failed += 1
                    logger.error(f"Failed to create collection {collection_name}: {result.error}")

            except Exception as e:
                collections_failed += 1
                logger.error(f"Error creating collection {collection_name}: {e}")

        logger.info(
            f"Tenant {tenant_id} collections: {collections_created} created, {collections_already_exist} already existed, {collections_failed} failed"
        )

        return {
            "success": collections_failed == 0,
            "collections_created": collections_created,
            "collections_already_exist": collections_already_exist,
            "collections_failed": collections_failed
        }
        
    except Exception as e:
        logger.error(f"Error creating collections for tenant {tenant_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

