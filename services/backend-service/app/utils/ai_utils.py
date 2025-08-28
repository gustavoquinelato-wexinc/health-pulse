"""
AI Utilities for Backend Service - Pulse AI Evolution Plan Phase 1-2
Provides helper functions for AI operations, embeddings, and ML monitoring.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.unified_models import AILearningMemory, AIPrediction, AIPerformanceMetric

logger = logging.getLogger(__name__)


class AIEmbeddingManager:
    """Manages vector embeddings for database entities."""
    
    @staticmethod
    def create_embedding_vector(dimensions: int = 1536) -> List[float]:
        """
        Create a placeholder embedding vector.
        In production, this would call OpenAI's text-embedding-3-small API.
        
        Args:
            dimensions: Vector dimensions (default 1536 for text-embedding-3-small)
            
        Returns:
            List of floats representing the embedding vector
        """
        # Placeholder implementation - in production, integrate with OpenAI API
        import random
        return [random.uniform(-1.0, 1.0) for _ in range(dimensions)]
    
    @staticmethod
    def update_entity_embedding(
        db: Session,
        table_name: str,
        entity_id: int,
        text_content: str,
        client_id: int
    ) -> bool:
        """
        Update an entity's embedding vector based on its text content.
        
        Args:
            db: Database session
            table_name: Name of the table to update
            entity_id: ID of the entity to update
            text_content: Text content to generate embedding from
            client_id: Client ID for multi-tenancy
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding (placeholder - integrate with OpenAI in production)
            embedding = AIEmbeddingManager.create_embedding_vector()
            
            # Update the entity's embedding column
            query = text(f"""
                UPDATE {table_name} 
                SET embedding = :embedding 
                WHERE id = :entity_id AND client_id = :client_id
            """)
            
            db.execute(query, {
                'embedding': embedding,
                'entity_id': entity_id,
                'client_id': client_id
            })
            db.commit()
            
            logger.info(f"Updated embedding for {table_name} ID {entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update embedding for {table_name} ID {entity_id}: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def similarity_search(
        db: Session,
        table_name: str,
        query_embedding: List[float],
        client_id: int,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using vector embeddings.
        
        Args:
            db: Database session
            table_name: Name of the table to search
            query_embedding: Query embedding vector
            client_id: Client ID for multi-tenancy
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of similar entities with similarity scores
        """
        try:
            # Use cosine similarity for vector search
            query = text(f"""
                SELECT id, 1 - (embedding <=> :query_embedding) as similarity_score
                FROM {table_name}
                WHERE client_id = :client_id 
                AND embedding IS NOT NULL
                AND 1 - (embedding <=> :query_embedding) >= :threshold
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """)
            
            result = db.execute(query, {
                'query_embedding': query_embedding,
                'client_id': client_id,
                'threshold': similarity_threshold,
                'limit': limit
            })
            
            return [{'id': row.id, 'similarity_score': row.similarity_score} for row in result]
            
        except Exception as e:
            logger.error(f"Similarity search failed for {table_name}: {e}")
            return []


class AILearningManager:
    """Manages AI learning and feedback collection."""
    
    @staticmethod
    def log_user_feedback(
        db: Session,
        client_id: int,
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
            client_id: Client ID
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
                client_id=client_id,
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
            
            logger.info(f"Logged AI learning feedback for client {client_id}")
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
        client_id: int,
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
            client_id: Client ID
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
                client_id=client_id,
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
            
            logger.info(f"Logged AI prediction for client {client_id}, model {model_name}")
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
                prediction.actual_outcome = json.dumps(actual_outcome)
                prediction.accuracy_score = accuracy_score
                prediction.validated_at = datetime.utcnow()
                
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
        client_id: int,
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
            client_id: Client ID
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
                client_id=client_id,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                service_name=service_name,
                context_data=json.dumps(context_data) if context_data else None
            )
            
            db.add(metric)
            db.commit()
            db.refresh(metric)
            
            logger.info(f"Logged performance metric {metric_name} for client {client_id}")
            return metric
            
        except Exception as e:
            logger.error(f"Failed to log performance metric: {e}")
            db.rollback()
            return None
