"""
AI Utilities for Backend Service - Phase 3-1 Clean Architecture
Provides helper functions for AI operations, Qdrant vector management, and ML monitoring.
Updated for Phase 3-1: No direct embedding column updates, uses Qdrant for vector storage.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.unified_models import AILearningMemory, AIPrediction, AIPerformanceMetric, QdrantVector

logger = logging.getLogger(__name__)


class QdrantVectorManager:
    """Manages vector operations with Qdrant for Phase 3-1 clean architecture."""

    @staticmethod
    def create_embedding_vector(dimensions: int = 1536) -> List[float]:
        """
        Create a placeholder embedding vector.
        In Phase 3-2, this will call configured AI providers (OpenAI, Azure, etc.).

        Args:
            dimensions: Vector dimensions (default 1536 for text-embedding-3-small)

        Returns:
            List of floats representing the embedding vector
        """
        # Placeholder implementation - Phase 3-2 will integrate with AI providers
        import random
        return [random.uniform(-1.0, 1.0) for _ in range(dimensions)]

    @staticmethod
    def store_entity_vector_in_qdrant(
        db: Session,
        table_name: str,
        entity_id: int,
        text_content: str,
        tenant_id: int,
        vector_type: str = "content"
    ) -> bool:
        """
        Store an entity's vector in Qdrant and track reference in PostgreSQL.
        Phase 3-1: Creates tracking record, Phase 3-2 will add actual Qdrant storage.

        Args:
            db: Database session
            table_name: Name of the source table
            entity_id: ID of the entity
            text_content: Text content to generate embedding from
            tenant_id: Tenant ID for multi-tenancy
            vector_type: Type of vector ('content', 'summary', 'metadata')

        Returns:
            True if successful, False otherwise
        """
        try:
            # Phase 3-1: Create tracking record only (no actual Qdrant storage yet)
            import uuid

            # Generate placeholder embedding for Phase 3-2
            embedding = QdrantVectorManager.create_embedding_vector()

            # Create Qdrant vector tracking record
            qdrant_vector = QdrantVector(
                tenant_id=tenant_id,
                table_name=table_name,
                record_id=entity_id,
                qdrant_collection=f"tenant_{tenant_id}_{table_name}",
                qdrant_point_id=str(uuid.uuid4()),
                vector_type=vector_type,
                embedding_model="text-embedding-3-small",  # Phase 3-2 will make this configurable
                embedding_provider="openai"  # Phase 3-2 will make this configurable
            )

            db.add(qdrant_vector)
            db.commit()

            logger.info(f"Created Qdrant vector tracking for {table_name} ID {entity_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store vector for {table_name} ID {entity_id}: {e}")
            db.rollback()
            return False

    @staticmethod
    def similarity_search_via_qdrant(
        db: Session,
        table_name: str,
        query_embedding: List[float],
        tenant_id: int,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using Qdrant vector database.
        Phase 3-1: Returns placeholder results, Phase 3-2 will implement actual Qdrant search.

        Args:
            db: Database session
            table_name: Name of the table to search
            query_embedding: Query embedding vector
            tenant_id: Tenant ID for multi-tenancy
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score

        Returns:
            List of similar entities with similarity scores
        """
        try:
            # Phase 3-1: Get available vector references from tracking table
            query = text("""
                SELECT record_id, qdrant_point_id, vector_type
                FROM qdrant_vectors
                WHERE tenant_id = :tenant_id
                AND table_name = :table_name
                ORDER BY last_updated_at DESC
                LIMIT :limit
            """)

            result = db.execute(query, {
                'tenant_id': tenant_id,
                'table_name': table_name,
                'limit': limit
            })

            # Phase 3-1: Return placeholder similarity scores
            # Phase 3-2: Will perform actual Qdrant similarity search
            return [
                {
                    'id': row.record_id,
                    'similarity_score': 0.85,  # Placeholder score
                    'qdrant_point_id': row.qdrant_point_id,
                    'vector_type': row.vector_type
                }
                for row in result
            ]

        except Exception as e:
            logger.error(f"Qdrant similarity search failed for {table_name}: {e}")
            return []


class AILearningManager:
    """Manages AI learning and feedback collection."""
    
    @staticmethod
    def log_user_feedback(
        db: Session,
        tenant_id: int,
        error_type: str,
        user_intent: str,
        failed_query: str,
        specific_issue: str,
        corrected_query: Optional[str] = None,
        user_feedback: Optional[str] = None,
        user_correction: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Optional[AILearningMemory]:
        """
        Log user feedback for AI learning improvement.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            error_type: Type of error encountered
            user_intent: What the user was trying to accomplish
            failed_query: The query that failed
            specific_issue: Specific issue description
            corrected_query: Corrected version of the query
            user_feedback: User's feedback
            user_correction: User's correction
            message_id: Associated message ID
            
        Returns:
            Created AILearningMemory instance or None if failed
        """
        try:
            learning_memory = AILearningMemory(
                tenant_id=tenant_id,
                error_type=error_type,
                user_intent=user_intent,
                failed_query=failed_query,
                specific_issue=specific_issue,
                corrected_query=corrected_query,
                user_feedback=user_feedback,
                user_correction=user_correction,
                message_id=message_id
            )
            
            db.add(learning_memory)
            db.commit()
            db.refresh(learning_memory)
            
            logger.info(f"Logged AI learning feedback for client {tenant_id}")
            return learning_memory
            
        except Exception as e:
            logger.error(f"Failed to log AI learning feedback: {e}")
            db.rollback()
            return None


class AIPredictionManager:
    """Manages AI predictions and accuracy tracking."""
    
    @staticmethod
    def log_prediction(
        db: Session,
        tenant_id: int,
        model_name: str,
        input_data: Dict[str, Any],
        prediction_result: Dict[str, Any],
        prediction_type: str,
        model_version: Optional[str] = None,
        confidence_score: Optional[float] = None
    ) -> Optional[AIPrediction]:
        """
        Log an AI model prediction.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            model_name: Name of the ML model
            input_data: Input data used for prediction
            prediction_result: Model's prediction result
            prediction_type: Type of prediction (trajectory, complexity, risk, etc.)
            model_version: Version of the model
            confidence_score: Confidence score of the prediction
            
        Returns:
            Created AIPrediction instance or None if failed
        """
        try:
            prediction = AIPrediction(
                tenant_id=tenant_id,
                model_name=model_name,
                model_version=model_version,
                input_data=json.dumps(input_data),
                prediction_result=json.dumps(prediction_result),
                confidence_score=confidence_score,
                prediction_type=prediction_type
            )
            
            db.add(prediction)
            db.commit()
            db.refresh(prediction)
            
            logger.info(f"Logged AI prediction for client {tenant_id}, model {model_name}")
            return prediction
            
        except Exception as e:
            logger.error(f"Failed to log AI prediction: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def update_prediction_accuracy(
        db: Session,
        prediction_id: int,
        actual_outcome: Dict[str, Any],
        accuracy_score: float
    ) -> bool:
        """
        Update a prediction with actual outcome and accuracy score.
        
        Args:
            db: Database session
            prediction_id: ID of the prediction to update
            actual_outcome: Actual outcome data
            accuracy_score: Calculated accuracy score
            
        Returns:
            True if successful, False otherwise
        """
        try:
            prediction = db.query(AIPrediction).filter(AIPrediction.id == prediction_id).first()
            if prediction:
                prediction.actual_outcome = json.dumps(actual_outcome)  # type: ignore
                prediction.accuracy_score = accuracy_score  # type: ignore
                prediction.validated_at = datetime.utcnow()  # type: ignore
                
                db.commit()
                logger.info(f"Updated prediction accuracy for prediction {prediction_id}")
                return True
            else:
                logger.warning(f"Prediction {prediction_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update prediction accuracy: {e}")
            db.rollback()
            return False


class AIPerformanceManager:
    """Manages AI performance metrics tracking."""
    
    @staticmethod
    def log_performance_metric(
        db: Session,
        tenant_id: int,
        metric_name: str,
        metric_value: float,
        service_name: str = "backend",
        metric_unit: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> Optional[AIPerformanceMetric]:
        """
        Log a performance metric for AI monitoring.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            metric_name: Name of the metric
            metric_value: Value of the metric
            service_name: Name of the service (backend, etl, ai)
            metric_unit: Unit of measurement
            context_data: Additional context data
            
        Returns:
            Created AIPerformanceMetric instance or None if failed
        """
        try:
            metric = AIPerformanceMetric(
                tenant_id=tenant_id,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                service_name=service_name,
                context_data=json.dumps(context_data) if context_data else None
            )
            
            db.add(metric)
            db.commit()
            db.refresh(metric)
            
            logger.info(f"Logged performance metric {metric_name} for client {tenant_id}")
            return metric
            
        except Exception as e:
            logger.error(f"Failed to log performance metric: {e}")
            db.rollback()
            return None
