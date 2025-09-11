"""
Client modules for ETL Service
"""

from .ai_client import AIClient, get_ai_client, generate_embeddings_for_etl

__all__ = ["AIClient", "get_ai_client", "generate_embeddings_for_etl"]
