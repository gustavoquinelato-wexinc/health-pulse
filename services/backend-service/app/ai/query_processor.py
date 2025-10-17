"""
AI Query Processor - Phase 3-6 Natural Language Query Interface
Processes natural language queries using hybrid AI providers and semantic search.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

from .hybrid_provider_manager import HybridProviderManager
from .qdrant_client import PulseQdrantClient
from ..models.unified_models import QdrantVector

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    """AI query result with sources"""
    success: bool
    answer: str
    sources: List[Dict[str, Any]]
    processing_time: float
    query_type: str  # 'semantic', 'structured', 'hybrid'
    confidence: float
    tenant_id: int
    metadata: Dict[str, Any]

class AIQueryProcessor:
    """Process natural language queries using hybrid AI providers"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.hybrid_provider_manager = HybridProviderManager(db_session)
        self.qdrant_client = PulseQdrantClient()

    async def initialize(self, tenant_id: int):
        """Initialize query processor"""
        await self.hybrid_provider_manager.initialize_providers(tenant_id)
        await self.qdrant_client.initialize()
        logger.info(f"AI Query Processor initialized for tenant {tenant_id}")

    async def process_query(self, query: str, tenant_id: int,
                          context: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Process natural language query"""
        start_time = time.time()
        
        try:
            # Analyze query intent
            query_intent = await self._analyze_query_intent(query, tenant_id)
            
            # Route to appropriate processing method
            if query_intent["type"] == "semantic":
                result = await self._process_semantic_query(query, tenant_id, query_intent)
            elif query_intent["type"] == "structured":
                result = await self._process_structured_query(query, tenant_id, query_intent)
            else:
                result = await self._process_hybrid_query(query, tenant_id, query_intent)
            
            processing_time = time.time() - start_time
            
            return QueryResult(
                success=True,
                answer=result["answer"],
                sources=result["sources"],
                processing_time=processing_time,
                query_type=query_intent["type"],
                confidence=result["confidence"],
                tenant_id=tenant_id,
                metadata={
                    "intent": query_intent,
                    "steps": result["steps"],
                    "context": context or {}
                }
            )
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return QueryResult(
                success=False,
                answer=f"I encountered an error processing your query: {str(e)}",
                sources=[],
                processing_time=time.time() - start_time,
                query_type="error",
                confidence=0.0,
                tenant_id=tenant_id,
                metadata={"error": str(e), "context": context or {}}
            )

    async def _analyze_query_intent(self, query: str, tenant_id: int) -> Dict[str, Any]:
        """Analyze query to determine processing approach"""
        try:
            # Use AI provider to analyze query intent
            prompt = f"""Analyze this query and determine the best processing approach:
Query: "{query}"

Respond with JSON:
{{
    "type": "semantic|structured|hybrid",
    "entities": ["list", "of", "key", "entities"],
    "intent": "brief description of what user wants",
    "complexity": "low|medium|high"
}}"""

            provider_response = await self.hybrid_provider_manager.generate_text(
                prompt=prompt,
                tenant_id=tenant_id,
                preferred_provider="auto"
            )
            
            if provider_response.success:
                try:
                    intent_data = json.loads(provider_response.data)
                    return intent_data
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse intent analysis JSON: {provider_response.data}")
            
            # Fallback to simple heuristics
            return self._fallback_intent_analysis(query)
            
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return self._fallback_intent_analysis(query)

    def _fallback_intent_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback intent analysis using simple heuristics"""
        query_lower = query.lower()
        
        # Simple keyword-based classification
        semantic_keywords = ["similar", "like", "related", "find", "search", "discover"]
        structured_keywords = ["count", "sum", "average", "total", "how many", "show me"]
        
        has_semantic = any(keyword in query_lower for keyword in semantic_keywords)
        has_structured = any(keyword in query_lower for keyword in structured_keywords)
        
        if has_semantic and has_structured:
            query_type = "hybrid"
        elif has_semantic:
            query_type = "semantic"
        elif has_structured:
            query_type = "structured"
        else:
            query_type = "hybrid"  # Default to hybrid for unknown queries
        
        return {
            "type": query_type,
            "entities": [],
            "intent": "User query analysis",
            "complexity": "medium"
        }

    async def _process_semantic_query(self, query: str, tenant_id: int,
                                    intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process query using semantic search"""
        try:
            # Generate embedding for the query
            embedding_response = await self.hybrid_provider_manager.generate_embeddings(
                texts=[query],
                tenant_id=tenant_id,
                preferred_provider="auto"
            )

            if not embedding_response.success:
                return {
                    "answer": "I couldn't process your semantic query.",
                    "sources": [],
                    "confidence": 0.0,
                    "steps": ["embedding_generation_failed"]
                }

            query_vector = embedding_response.data[0]

            # Search across relevant collections
            collections_to_search = [
                f"client_{tenant_id}_work_items",
                f"client_{tenant_id}_prs",
                f"client_{tenant_id}_prs_comments",
                f"client_{tenant_id}_projects"
            ]

            all_results = []
            for collection_name in collections_to_search:
                try:
                    search_results = await self.qdrant_client.search_vectors(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=5,
                        score_threshold=0.7
                    )

                    # Convert VectorSearchResult to dict format
                    for result in search_results:
                        all_results.append({
                            "id": result.id,
                            "score": result.score,
                            "payload": result.payload,
                            "collection": collection_name
                        })

                except Exception as e:
                    logger.warning(f"Search failed for collection {collection_name}: {e}")
                    continue

            # Sort by score and limit results
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_results = all_results[:10]

            # Generate response based on results
            if top_results:
                response = f"I found {len(top_results)} semantically similar items related to your query."
                confidence = max(result.get("score", 0) for result in top_results)
            else:
                response = "I couldn't find any semantically similar items for your query."
                confidence = 0.0

            return {
                "answer": response,
                "sources": top_results,
                "confidence": confidence,
                "steps": ["embedding_generation", "semantic_search", "response_generation"]
            }

        except Exception as e:
            logger.error(f"Semantic query processing failed: {e}")
            return {
                "answer": "I couldn't process your semantic query.",
                "sources": [],
                "confidence": 0.0,
                "steps": ["error"]
            }

    async def _process_structured_query(self, query: str, tenant_id: int,
                                       intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process query using structured database queries"""
        try:
            # Use AI to generate SQL query
            prompt = f"""Convert this natural language query to SQL for a PostgreSQL database:
Query: "{query}"

Available tables: work_items, prs, prs_comments, projects, users
All tables have tenant_id column for filtering.
IMPORTANT: Always include 'WHERE tenant_id = {tenant_id}' in your queries.

Return only the SQL query, no explanation."""

            provider_response = await self.hybrid_provider_manager.generate_text(
                prompt=prompt,
                tenant_id=tenant_id,
                preferred_provider="auto"
            )

            if not provider_response.success:
                return {
                    "answer": "I couldn't generate a SQL query for your request.",
                    "sources": [],
                    "confidence": 0.0,
                    "steps": ["sql_generation_failed"]
                }

            sql_query = provider_response.data.strip()

            # Basic SQL validation (simplified)
            if not sql_query.lower().startswith('select'):
                return {
                    "answer": "I can only process SELECT queries for safety.",
                    "sources": [],
                    "confidence": 0.0,
                    "steps": ["sql_validation_failed"]
                }

            # Execute SQL query (with safety limits)
            try:
                result = self.db_session.execute(
                    text(sql_query + " LIMIT 100")  # Safety limit
                )
                rows = result.fetchall()
                columns = result.keys()

                # Convert to list of dictionaries
                results = [dict(zip(columns, row)) for row in rows]

                # Generate response
                response = f"Based on your query, I found {len(results)} results."

                return {
                    "answer": response,
                    "sources": results,
                    "confidence": 0.8,
                    "steps": ["sql_generation", "query_execution", "response_generation"],
                    "sql_query": sql_query
                }

            except Exception as e:
                logger.error(f"SQL execution failed: {e}")
                return {
                    "answer": "I couldn't execute the generated SQL query.",
                    "sources": [],
                    "confidence": 0.0,
                    "steps": ["sql_execution_failed"],
                    "sql_query": sql_query,
                    "error": str(e)
                }

        except Exception as e:
            logger.error(f"Structured query processing failed: {e}")
            return {
                "answer": "I couldn't process your structured query.",
                "sources": [],
                "confidence": 0.0,
                "steps": ["error"]
            }

    async def _process_hybrid_query(self, query: str, tenant_id: int,
                                  intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process query using both semantic and structured approaches"""
        try:
            # Run both semantic and structured processing
            semantic_result = await self._process_semantic_query(query, tenant_id, intent)
            structured_result = await self._process_structured_query(query, tenant_id, intent)

            # Combine results intelligently
            combined_sources = semantic_result["sources"] + structured_result["sources"]

            # Generate combined response
            semantic_count = len(semantic_result["sources"])
            structured_count = len(structured_result["sources"])

            if semantic_count > 0 and structured_count > 0:
                response = f"I found information using both semantic search ({semantic_count} items) and database queries ({structured_count} items). {semantic_result['answer']}"
            elif semantic_count > 0:
                response = f"Using semantic search: {semantic_result['answer']}"
            elif structured_count > 0:
                response = f"Using database queries: {structured_result['answer']}"
            else:
                response = "I couldn't find relevant information using either semantic search or database queries."

            return {
                "answer": response,
                "sources": combined_sources[:15],  # Limit combined sources
                "confidence": max(semantic_result["confidence"], structured_result["confidence"]),
                "steps": ["hybrid_processing", "semantic_search", "structured_query", "result_combination"]
            }

        except Exception as e:
            logger.error(f"Hybrid query processing failed: {e}")
            return {
                "answer": "I couldn't process your query using hybrid approach.",
                "sources": [],
                "confidence": 0.0,
                "steps": ["error"]
            }

    async def semantic_search(self, query: str, tenant_id: int,
                            collections: Optional[List[str]] = None,
                            limit: int = 10) -> Dict[str, Any]:
        """Perform semantic search across specified collections"""
        try:
            # Generate embedding for the query
            embedding_response = await self.hybrid_provider_manager.generate_embeddings(
                texts=[query],
                tenant_id=tenant_id,
                preferred_provider="auto"
            )

            if not embedding_response.success:
                return {
                    "success": False,
                    "results": [],
                    "error": "Failed to generate query embedding"
                }

            query_vector = embedding_response.data[0]

            # Use provided collections or default ones
            if not collections:
                collections = [
                    f"client_{tenant_id}_work_items",
                    f"client_{tenant_id}_prs",
                    f"client_{tenant_id}_prs_comments",
                    f"client_{tenant_id}_projects"
                ]

            all_results = []
            for collection_name in collections:
                try:
                    search_results = await self.qdrant_client.search_vectors(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=limit,
                        score_threshold=0.6
                    )

                    # Convert VectorSearchResult to dict format
                    for result in search_results:
                        all_results.append({
                            "id": result.id,
                            "score": result.score,
                            "payload": result.payload,
                            "collection": collection_name
                        })

                except Exception as e:
                    logger.warning(f"Search failed for collection {collection_name}: {e}")
                    continue

            # Sort by score and limit results
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_results = all_results[:limit]

            return {
                "success": True,
                "results": top_results,
                "total_found": len(all_results),
                "collections_searched": collections
            }

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return {
                "success": False,
                "results": [],
                "error": str(e)
            }

    async def get_capabilities(self, tenant_id: int) -> Dict[str, Any]:
        """Get AI query capabilities for this tenant"""
        try:
            # Providers should already be initialized

            # Check available collections
            collections = []
            collection_names = [
                f"client_{tenant_id}_work_items",
                f"client_{tenant_id}_prs",
                f"client_{tenant_id}_prs_comments",
                f"client_{tenant_id}_projects",
                f"client_{tenant_id}_changelogs"
            ]

            for collection_name in collection_names:
                try:
                    info = await self.qdrant_client.get_collection_info(collection_name)
                    if info.success:
                        collections.append({
                            "name": collection_name,
                            "vector_count": info.data.get("vectors_count", 0),
                            "status": "available"
                        })
                except:
                    collections.append({
                        "name": collection_name,
                        "vector_count": 0,
                        "status": "unavailable"
                    })

            return {
                "success": True,
                "capabilities": {
                    "natural_language_queries": True,
                    "semantic_search": True,
                    "structured_queries": True,
                    "hybrid_processing": True
                },
                "collections": collections,
                "query_types": ["semantic", "structured", "hybrid"],
                "tenant_id": tenant_id
            }

        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def cleanup(self):
        """Cleanup AI providers to prevent event loop errors"""
        try:
            if hasattr(self, 'hybrid_provider_manager') and self.hybrid_provider_manager:
                await self.hybrid_provider_manager.cleanup()
                logger.debug("AIQueryProcessor cleaned up hybrid provider manager")
        except Exception as e:
            logger.warning(f"Error during AIQueryProcessor cleanup: {e}")
