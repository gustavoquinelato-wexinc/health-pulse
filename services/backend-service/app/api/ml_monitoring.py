"""
ML Monitoring API endpoints for Backend Service.
Provides read-only access to ML monitoring tables for Phase 1-4.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import timedelta

from app.core.database import get_read_session
from app.core.logging_config import get_logger
from app.models.unified_models import AILearningMemory, AIPrediction, MLAnomalyAlert
from app.auth.auth_middleware import UserData, require_authentication

router = APIRouter(prefix="/api/ml", tags=["ML Monitoring"])
logger = get_logger(__name__)


def require_admin_user(user: UserData = Depends(require_authentication)) -> UserData:
    """Require admin user for ML monitoring endpoints."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Admin privileges required for ML monitoring"
        )
    return user


@router.get("/learning-memory")
async def get_learning_memory(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    error_type: Optional[str] = Query(None, description="Filter by error type"),
    limit: int = Query(50, le=100, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get AI learning memory for analysis (admin only)"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        query = db.query(AILearningMemory).filter(
            AILearningMemory.tenant_id == tenant_id,
            AILearningMemory.active == True
        )
        
        if error_type:
            query = query.filter(AILearningMemory.error_type == error_type)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        memories = query.order_by(AILearningMemory.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for memory in memories:
            memory_dict = memory.to_dict()
            result.append(memory_dict)
        
        return {
            "learning_memories": result,
            "count": len(result),
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "filters": {
                "error_type": error_type,
                "tenant_id": tenant_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching learning memory: {e}")
        raise HTTPException(500, f"Failed to fetch learning memory: {str(e)}")


@router.get("/predictions")
async def get_predictions(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    prediction_type: Optional[str] = Query(None, description="Filter by prediction type"),
    limit: int = Query(50, le=100, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get AI predictions for monitoring (admin only)"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        query = db.query(AIPrediction).filter(
            AIPrediction.tenant_id == tenant_id,
            AIPrediction.active == True
        )
        
        if model_name:
            query = query.filter(AIPrediction.model_name == model_name)
            
        if prediction_type:
            query = query.filter(AIPrediction.prediction_type == prediction_type)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        predictions = query.order_by(AIPrediction.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for prediction in predictions:
            prediction_dict = prediction.to_dict()
            result.append(prediction_dict)
        
        return {
            "predictions": result,
            "count": len(result),
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "filters": {
                "model_name": model_name,
                "prediction_type": prediction_type,
                "tenant_id": tenant_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        raise HTTPException(500, f"Failed to fetch predictions: {str(e)}")


@router.get("/anomaly-alerts")
async def get_anomaly_alerts(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    limit: int = Query(50, le=100, description="Maximum number of alerts to return"),
    offset: int = Query(0, ge=0, description="Number of alerts to skip for pagination"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get ML anomaly alerts for monitoring (admin only)"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        query = db.query(MLAnomalyAlert).filter(
            MLAnomalyAlert.tenant_id == tenant_id,
            MLAnomalyAlert.active == True
        )
        
        if acknowledged is not None:
            query = query.filter(MLAnomalyAlert.acknowledged == acknowledged)
            
        if severity:
            query = query.filter(MLAnomalyAlert.severity == severity)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        alerts = query.order_by(MLAnomalyAlert.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for alert in alerts:
            alert_dict = alert.to_dict()
            result.append(alert_dict)
        
        return {
            "anomaly_alerts": result,
            "count": len(result),
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "filters": {
                "acknowledged": acknowledged,
                "severity": severity,
                "tenant_id": tenant_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching anomaly alerts: {e}")
        raise HTTPException(500, f"Failed to fetch anomaly alerts: {str(e)}")


@router.get("/stats")
async def get_ml_stats(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    days: int = Query(30, ge=1, le=365, description="Number of days to include in stats"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get ML monitoring statistics (admin only)"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Calculate date range
        from app.core.utils import DateTimeHelper
        end_date = DateTimeHelper.now_default()
        start_date = end_date - timedelta(days=days)
        
        # Get learning memory stats
        learning_memory_count = db.query(func.count(AILearningMemory.id)).filter(
            AILearningMemory.tenant_id == tenant_id,
            AILearningMemory.active == True,
            AILearningMemory.created_at >= start_date
        ).scalar()
        
        # Get prediction stats
        prediction_count = db.query(func.count(AIPrediction.id)).filter(
            AIPrediction.tenant_id == tenant_id,
            AIPrediction.active == True,
            AIPrediction.created_at >= start_date
        ).scalar()
        
        # Get anomaly alert stats
        alert_count = db.query(func.count(MLAnomalyAlert.id)).filter(
            MLAnomalyAlert.tenant_id == tenant_id,
            MLAnomalyAlert.active == True,
            MLAnomalyAlert.created_at >= start_date
        ).scalar()
        
        unacknowledged_alerts = db.query(func.count(MLAnomalyAlert.id)).filter(
            MLAnomalyAlert.tenant_id == tenant_id,
            MLAnomalyAlert.active == True,
            MLAnomalyAlert.acknowledged == False,
            MLAnomalyAlert.created_at >= start_date
        ).scalar()
        
        # Get model usage stats
        model_stats = db.query(
            AIPrediction.model_name,
            func.count(AIPrediction.id).label('prediction_count')
        ).filter(
            AIPrediction.tenant_id == tenant_id,
            AIPrediction.active == True,
            AIPrediction.created_at >= start_date
        ).group_by(AIPrediction.model_name).all()
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "learning_memories": learning_memory_count,
                "predictions": prediction_count,
                "anomaly_alerts": alert_count,
                "unacknowledged_alerts": unacknowledged_alerts
            },
            "model_usage": [
                {"model_name": stat.model_name, "prediction_count": stat.prediction_count}
                for stat in model_stats
            ],
            "tenant_id": tenant_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ML stats: {e}")
        raise HTTPException(500, f"Failed to fetch ML statistics: {str(e)}")


@router.get("/health")
async def get_ml_monitoring_health(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get ML monitoring system health (admin only)"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Test table accessibility
        table_status = {}
        tables = [
            ('ai_learning_memory', AILearningMemory),
            ('ai_predictions', AIPrediction),
            ('ml_anomaly_alerts', MLAnomalyAlert)
        ]
        
        for table_name, model_class in tables:
            try:
                count = db.query(func.count(model_class.id)).filter(
                    model_class.tenant_id == tenant_id,
                    model_class.active == True
                ).scalar()
                table_status[table_name] = {
                    "accessible": True,
                    "record_count": count
                }
            except Exception as e:
                table_status[table_name] = {
                    "accessible": False,
                    "error": str(e)
                }
        
        # Determine overall health
        all_accessible = all(status["accessible"] for status in table_status.values())
        
        from app.core.utils import DateTimeHelper
        return {
            "status": "healthy" if all_accessible else "degraded",
            "tables": table_status,
            "tenant_id": tenant_id,
            "timestamp": DateTimeHelper.now_default()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking ML monitoring health: {e}")
        raise HTTPException(500, f"Failed to check ML monitoring health: {str(e)}")
