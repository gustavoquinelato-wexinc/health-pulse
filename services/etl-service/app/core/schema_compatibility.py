"""
Schema Compatibility Utilities for Phase 1-3: ETL Jobs Compatibility

Provides utilities for validating and handling enhanced schema compatibility
in GitHub and Jira ETL jobs. Ensures graceful handling of embedding fields
and other ML-related enhancements.
"""

from typing import Dict, Any, List, Optional, Type
from sqlalchemy.orm import Session
from app.core.logging_config import get_logger
from app.models.unified_models import Base

logger = get_logger(__name__)


class SchemaCompatibilityValidator:
    """Validates schema compatibility for ETL operations."""
    
    # Models that have embedding fields for ML enhancement
    ML_ENHANCED_MODELS = {
        'Repository', 'PullRequest', 'PullRequestReview', 'PullRequestCommit', 
        'PullRequestComment', 'Issue', 'Project', 'JiraPullRequestLinks',
        'Status', 'Issuetype', 'IssueChangelog'
    }
    
    def __init__(self, job_name: str = "ETL"):
        """
        Initialize schema compatibility validator.
        
        Args:
            job_name: Name of the ETL job for logging context
        """
        self.job_name = job_name
        self.validation_errors = []
        self.compatibility_warnings = []
    
    def validate_model_data(self, model_class: Type[Base], data: Dict[str, Any], 
                          context: str = "") -> bool:
        """
        Validate that data is compatible with enhanced model schema.
        
        Args:
            model_class: SQLAlchemy model class
            data: Data dictionary to validate
            context: Additional context for error reporting
            
        Returns:
            True if data is valid, False otherwise
        """
        try:
            model_name = model_class.__name__
            
            # Check if this is an ML-enhanced model
            is_ml_enhanced = model_name in self.ML_ENHANCED_MODELS
            
            # Validate required fields exist
            if not self._validate_required_fields(model_class, data, context):
                return False
            
            # For ML-enhanced models, ensure embedding field handling
            if is_ml_enhanced:
                self._validate_embedding_compatibility(data, model_name, context)
            
            # Log successful validation
            if is_ml_enhanced:
                logger.debug(f"✅ [{self.job_name}] {model_name} data validated with ML schema compatibility {context}")
            else:
                logger.debug(f"✅ [{self.job_name}] {model_name} data validated {context}")
            
            return True
            
        except Exception as e:
            error_msg = f"Schema validation error for {model_class.__name__} {context}: {e}"
            self.validation_errors.append(error_msg)
            logger.error(f"❌ [{self.job_name}] {error_msg}")
            return False
    
    def _validate_required_fields(self, model_class: Type[Base], data: Dict[str, Any], 
                                context: str) -> bool:
        """Validate that required fields are present in data."""
        # Basic validation - ensure data is not empty
        if not data:
            error_msg = f"Empty data provided for {model_class.__name__} {context}"
            self.validation_errors.append(error_msg)
            return False
        
        # Check for basic required fields that all models should have
        basic_required = ['client_id', 'integration_id', 'active']
        missing_fields = [field for field in basic_required if field not in data]
        
        if missing_fields:
            error_msg = f"Missing required fields for {model_class.__name__} {context}: {missing_fields}"
            self.validation_errors.append(error_msg)
            return False
        
        return True
    
    def _validate_embedding_compatibility(self, data: Dict[str, Any], model_name: str, 
                                        context: str) -> None:
        """Validate embedding field compatibility for ML-enhanced models."""
        # Check if embedding field is explicitly set
        if 'embedding' in data:
            if data['embedding'] is not None:
                warning_msg = f"Embedding field explicitly set to non-None for {model_name} {context} - should be None in Phase 1"
                self.compatibility_warnings.append(warning_msg)
                logger.warning(f"⚠️ [{self.job_name}] {warning_msg}")
        else:
            # This is expected - embedding will default to None in the model
            logger.debug(f"✅ [{self.job_name}] {model_name} {context} - embedding field will default to None")
    
    def validate_bulk_data(self, model_class: Type[Base], data_list: List[Dict[str, Any]], 
                          operation_name: str = "") -> bool:
        """
        Validate bulk data for schema compatibility.
        
        Args:
            model_class: SQLAlchemy model class
            data_list: List of data dictionaries
            operation_name: Name of the bulk operation for context
            
        Returns:
            True if all data is valid, False if any validation fails
        """
        if not data_list:
            logger.warning(f"⚠️ [{self.job_name}] Empty data list for bulk {operation_name}")
            return True
        
        model_name = model_class.__name__
        is_ml_enhanced = model_name in self.ML_ENHANCED_MODELS
        
        logger.info(f"🔍 [{self.job_name}] Validating {len(data_list)} {model_name} records for bulk {operation_name}")
        
        valid_count = 0
        for i, data in enumerate(data_list):
            if self.validate_model_data(model_class, data, f"bulk item {i+1}"):
                valid_count += 1
        
        success_rate = (valid_count / len(data_list)) * 100
        
        if valid_count == len(data_list):
            if is_ml_enhanced:
                logger.info(f"✅ [{self.job_name}] All {len(data_list)} {model_name} records validated for ML-enhanced bulk {operation_name}")
            else:
                logger.info(f"✅ [{self.job_name}] All {len(data_list)} {model_name} records validated for bulk {operation_name}")
            return True
        else:
            logger.error(f"❌ [{self.job_name}] Bulk validation failed: {valid_count}/{len(data_list)} records valid ({success_rate:.1f}%)")
            return False
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results."""
        return {
            'job_name': self.job_name,
            'errors_count': len(self.validation_errors),
            'warnings_count': len(self.compatibility_warnings),
            'errors': self.validation_errors,
            'warnings': self.compatibility_warnings,
            'has_errors': len(self.validation_errors) > 0,
            'has_warnings': len(self.compatibility_warnings) > 0
        }
    
    def log_validation_summary(self) -> None:
        """Log validation summary."""
        summary = self.get_validation_summary()
        
        if summary['has_errors']:
            logger.error(f"❌ [{self.job_name}] Schema validation completed with {summary['errors_count']} errors")
            for error in summary['errors']:
                logger.error(f"   • {error}")
        
        if summary['has_warnings']:
            logger.warning(f"⚠️ [{self.job_name}] Schema validation completed with {summary['warnings_count']} warnings")
            for warning in summary['warnings']:
                logger.warning(f"   • {warning}")
        
        if not summary['has_errors'] and not summary['has_warnings']:
            logger.info(f"✅ [{self.job_name}] Schema validation completed successfully - no issues detected")


def safe_model_creation(model_class: Type[Base], data: Dict[str, Any], 
                       context: str = "", job_name: str = "ETL") -> Optional[Base]:
    """
    Safely create a model instance with schema compatibility validation.
    
    Args:
        model_class: SQLAlchemy model class
        data: Data dictionary for model creation
        context: Additional context for error reporting
        job_name: Name of the ETL job for logging
        
    Returns:
        Model instance if successful, None if failed
    """
    validator = SchemaCompatibilityValidator(job_name)
    
    try:
        # Validate data before model creation
        if not validator.validate_model_data(model_class, data, context):
            logger.error(f"❌ [{job_name}] Model creation failed validation for {model_class.__name__} {context}")
            return None
        
        # Create model instance
        instance = model_class(**data)
        
        # Log successful creation
        model_name = model_class.__name__
        is_ml_enhanced = model_name in validator.ML_ENHANCED_MODELS
        
        if is_ml_enhanced:
            logger.debug(f"✅ [{job_name}] Created {model_name} with ML schema compatibility {context}")
        else:
            logger.debug(f"✅ [{job_name}] Created {model_name} {context}")
        
        return instance
        
    except Exception as e:
        logger.error(f"❌ [{job_name}] Error creating {model_class.__name__} {context}: {e}")
        return None


def log_schema_compatibility_status(table_name: str, record_count: int, 
                                  job_name: str = "ETL") -> None:
    """
    Log schema compatibility status for bulk operations.
    
    Args:
        table_name: Name of the database table
        record_count: Number of records processed
        job_name: Name of the ETL job for logging
    """
    validator = SchemaCompatibilityValidator(job_name)
    
    # Check if this table corresponds to an ML-enhanced model
    model_name = table_name.replace('_', '').title().replace('s', '')  # Simple conversion
    is_ml_enhanced = any(model in table_name.lower() for model in 
                        ['issue', 'project', 'repository', 'pull_request', 'status'])
    
    if is_ml_enhanced:
        logger.info(f"✅ [{job_name}] Processed {record_count} {table_name} records with ML schema compatibility")
    else:
        logger.info(f"✅ [{job_name}] Processed {record_count} {table_name} records")
