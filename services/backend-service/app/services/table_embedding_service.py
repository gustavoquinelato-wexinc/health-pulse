"""
Table-specific embedding service for admin pages.
Provides direct embedding of specific tables without job queue system.
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_database
from app.ai.qdrant_client import PulseQdrantClient
from app.ai.hybrid_provider_manager import HybridProviderManager
from app.models.unified_models import (
    WitHierarchy, WitMapping, StatusMapping, Workflow,
    WorkItem, Status, Wit, Project, Repository, Pr,
    PrComment, PrCommit, PrReview, Changelog, QdrantVector
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TableEmbeddingService:
    """Service for direct table embedding without queue system."""
    
    def __init__(self):
        self.qdrant_client = None
        self.hybrid_provider = None
        
    async def _get_qdrant_client(self) -> PulseQdrantClient:
        """Get or create Qdrant client."""
        if not self.qdrant_client:
            self.qdrant_client = PulseQdrantClient()
        return self.qdrant_client
    
    async def _get_hybrid_provider(self) -> HybridProviderManager:
        """Get or create hybrid provider."""
        if not self.hybrid_provider:
            self.hybrid_provider = HybridProviderManager()
        return self.hybrid_provider
    
    def _validate_table_name(self, table_name: str) -> bool:
        """Validate if table name is supported."""
        supported_tables = [
            'work_items', 'changelogs', 'projects', 'statuses', 'wits',
            'prs', 'prs_commits', 'prs_reviews', 'prs_comments', 'repositories',
            'wits_hierarchies', 'wits_mappings', 'statuses_mappings', 'workflows'
        ]
        return table_name in supported_tables
    
    async def start_table_embedding(
        self,
        table_name: str,
        tenant_id: int,
        integration_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Start embedding process for a specific table.
        
        Args:
            table_name: Name of the table to embed
            tenant_id: Tenant ID
            integration_id: Optional integration filter
            
        Returns:
            Dict with session details and results
        """
        session_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            logger.info(f"Starting table embedding for {table_name}, tenant {tenant_id}")
            
            # Get entities to embed
            entities = await self._get_entities_to_embed(table_name, tenant_id, integration_id)
            
            if not entities:
                return {
                    'session_id': session_id,
                    'table_name': table_name,
                    'tenant_id': tenant_id,
                    'total_entities': 0,
                    'processed_entities': 0,
                    'status': 'completed',
                    'message': f'No entities found in {table_name} for embedding',
                    'duration_seconds': time.time() - start_time
                }
            
            # Process entities
            processed_count = 0
            for entity in entities:
                try:
                    await self._embed_entity(entity, table_name, tenant_id)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to embed {table_name} entity {entity.get('id', 'unknown')}: {e}")
            
            duration = time.time() - start_time
            
            return {
                'session_id': session_id,
                'table_name': table_name,
                'tenant_id': tenant_id,
                'total_entities': len(entities),
                'processed_entities': processed_count,
                'status': 'completed',
                'message': f'Successfully embedded {processed_count}/{len(entities)} entities',
                'duration_seconds': duration
            }
            
        except Exception as e:
            logger.error(f"Table embedding failed for {table_name}: {e}")
            return {
                'session_id': session_id,
                'table_name': table_name,
                'tenant_id': tenant_id,
                'total_entities': 0,
                'processed_entities': 0,
                'status': 'failed',
                'message': f'Embedding failed: {str(e)}',
                'duration_seconds': time.time() - start_time
            }
    
    async def _get_entities_to_embed(
        self,
        table_name: str,
        tenant_id: int,
        integration_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get entities from database for embedding."""
        # This is a simplified version - in practice you'd implement
        # specific queries for each table type
        return []
    
    async def _embed_entity(
        self,
        entity: Dict[str, Any],
        table_name: str,
        tenant_id: int
    ) -> None:
        """Embed a single entity."""
        # This is a simplified version - in practice you'd implement
        # the full embedding pipeline
        pass


# Global service instance
table_embedding_service = TableEmbeddingService()
