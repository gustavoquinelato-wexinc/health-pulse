"""
Embedding Model Consistency Validator

Prevents mixed embedding models per tenant to ensure vector compatibility.
"""

from app.core.database import get_database
from app.models.unified_models import QdrantVector, Integration
from sqlalchemy import func, distinct
import logging

logger = logging.getLogger(__name__)

class EmbeddingModelValidator:
    """Validates embedding model consistency per tenant"""
    
    @staticmethod
    async def validate_tenant_model_consistency(tenant_id: int, new_model: str, new_dimensions: int) -> bool:
        """
        Validate that new embedding model is compatible with existing vectors
        
        Returns:
            True: Safe to use this model
            False: Would create incompatible mixed models
        """
        database = get_database()
        with database.get_read_session_context() as session:
            
            # Check existing models for this tenant
            existing_models = session.query(
                distinct(QdrantVector.embedding_model),
                QdrantVector.embedding_dimensions
            ).filter(
                QdrantVector.tenant_id == tenant_id
            ).all()
            
            if not existing_models:
                # No existing vectors - any model is fine
                logger.info(f"Tenant {tenant_id}: No existing vectors, {new_model} approved")
                return True
            
            # Check if new model matches existing
            for existing_model, existing_dimensions in existing_models:
                if existing_model != new_model:
                    logger.error(f"Tenant {tenant_id}: Model mismatch! Existing: {existing_model}, New: {new_model}")
                    return False
                if existing_dimensions != new_dimensions:
                    logger.error(f"Tenant {tenant_id}: Dimension mismatch! Existing: {existing_dimensions}, New: {new_dimensions}")
                    return False
            
            logger.info(f"Tenant {tenant_id}: Model {new_model} is consistent with existing vectors")
            return True
    
    @staticmethod
    async def get_tenant_embedding_model(tenant_id: int) -> dict:
        """Get the current embedding model for a tenant"""
        database = get_database()
        with database.get_read_session_context() as session:
            
            result = session.query(
                QdrantVector.embedding_model,
                QdrantVector.embedding_provider,
                QdrantVector.embedding_dimensions,
                func.count(QdrantVector.id).label('vector_count')
            ).filter(
                QdrantVector.tenant_id == tenant_id
            ).group_by(
                QdrantVector.embedding_model,
                QdrantVector.embedding_provider,
                QdrantVector.embedding_dimensions
            ).first()
            
            if result:
                return {
                    'model': result.embedding_model,
                    'provider': result.embedding_provider,
                    'dimensions': result.embedding_dimensions,
                    'vector_count': result.vector_count
                }
            else:
                return None
    
    @staticmethod
    async def suggest_migration_if_needed(tenant_id: int, desired_model: str) -> dict:
        """Suggest migration strategy if model change is needed"""
        current_model = await EmbeddingModelValidator.get_tenant_embedding_model(tenant_id)
        
        if not current_model:
            return {
                'migration_needed': False,
                'message': f'No existing vectors, can use {desired_model} directly'
            }
        
        if current_model['model'] == desired_model:
            return {
                'migration_needed': False,
                'message': f'Already using {desired_model}'
            }
        
        return {
            'migration_needed': True,
            'current_model': current_model['model'],
            'desired_model': desired_model,
            'vector_count': current_model['vector_count'],
            'migration_options': [
                {
                    'option': 'full_re_vectorization',
                    'description': 'Delete all vectors and re-generate with new model',
                    'pros': ['Clean, consistent results', 'Optimal search quality'],
                    'cons': ['Processing time', 'API costs if using external model']
                },
                {
                    'option': 'separate_collections',
                    'description': 'Keep existing vectors, use new model for new data',
                    'pros': ['No re-processing', 'Immediate switch'],
                    'cons': ['Complex search logic', 'Suboptimal similarity results']
                }
            ]
        }

# Model dimension mapping
MODEL_DIMENSIONS = {
    'all-mpnet-base-v2': 768,
    'azure-text-embedding-3-small': 1536,
    'azure-text-embedding-3-large': 3072,
    'text-embedding-ada-002': 1536,
    'text-embedding-3-small': 1536,
    'text-embedding-3-large': 3072
}

def get_model_dimensions(model_name: str) -> int:
    """Get dimensions for a known model"""
    return MODEL_DIMENSIONS.get(model_name, 0)
