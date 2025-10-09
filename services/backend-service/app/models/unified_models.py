"""
Unified data models for Backend Service - Phase 3-1 Clean Architecture.
Based on existing snowflake_db_manager.py model with additions for development data and AI capabilities.
Updated for Phase 3-1: Vector columns removed, Qdrant integration, AI provider support.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Text, PrimaryKeyConstraint, func, Boolean, Index, text, UniqueConstraint, ARRAY, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator, Text as SQLText
from typing import Dict, Any, Optional, List, Union, TYPE_CHECKING
import json
from datetime import datetime, timezone
import uuid

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement




Base = declarative_base()


class Tenant(Base):
    """Tenants table to manage different tenant organizations."""
    __tablename__ = 'tenants'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    name = Column(String, nullable=False, quote=False, name="name")
    website = Column(String, nullable=True, quote=False, name="website")
    assets_folder = Column(String(100), nullable=True, quote=False, name="assets_folder")
    logo_filename = Column(String(255), nullable=True, default='default-logo.png', quote=False, name="logo_filename")
    color_schema_mode = Column(String(10), nullable=True, default='default', quote=False, name="color_schema_mode")
    active = Column(Boolean, nullable=False, default=True, quote=False, name="active")
    created_at = Column(DateTime, quote=False, name="created_at", default=func.now())
    last_updated_at = Column(DateTime, quote=False, name="last_updated_at", default=func.now())



    # Relationships - allows easy navigation to related data
    integrations = relationship("Integration", back_populates="tenant")
    projects = relationship("Project", back_populates="tenant")
    wits = relationship("Wit", back_populates="tenant")
    statuses = relationship("Status", back_populates="tenant")
    statuses_mappings = relationship("StatusMapping", back_populates="tenant")
    workflows = relationship("Workflow", back_populates="tenant")
    wits_mappings = relationship("WitMapping", back_populates="tenant")
    wits_hierarchies = relationship("WitHierarchy", back_populates="tenant")
    work_items = relationship("WorkItem", back_populates="tenant")
    changelogs = relationship("Changelog", back_populates="tenant")
    custom_fields = relationship("CustomField", back_populates="tenant")
    custom_field_mappings = relationship("CustomFieldMapping", back_populates="tenant")
    repositories = relationship("Repository", back_populates="tenant")
    prs = relationship("Pr", back_populates="tenant")
    prs_reviews = relationship("PrReview", back_populates="tenant")
    prs_commits = relationship("PrCommit", back_populates="tenant")
    prs_comments = relationship("PrComment", back_populates="tenant")
    work_items_prs_links = relationship("WorkItemPrLink", back_populates="tenant")
    system_settings = relationship("SystemSettings", back_populates="tenant")
    color_settings = relationship("TenantColors", back_populates="tenant")

    # AI Enhancement: ML monitoring relationships
    ai_learning_memories = relationship("AILearningMemory", back_populates="tenant")
    ai_predictions = relationship("AIPrediction", back_populates="tenant")
    ai_performance_metrics = relationship("AIPerformanceMetric", back_populates="tenant")
    ml_anomaly_alerts = relationship("MLAnomalyAlert", back_populates="tenant")

    # Phase 3-1: New AI architecture relationships
    qdrant_vectors = relationship("QdrantVector", back_populates="tenant")
    ai_usage_trackings = relationship("AIUsageTracking", back_populates="tenant")
    vectorization_queue = relationship("VectorizationQueue", back_populates="tenant")

    # Phase 2.1: Issue types discovery relationships
    projects_issue_types = relationship("ProjectIssueType", back_populates="tenant")

    # Phase 1: Raw extraction data relationships
    raw_extraction_data = relationship("RawExtractionData", back_populates="tenant")
    custom_fields = relationship("CustomField", back_populates="tenant")


class BaseEntity:
    """Base class with audit fields for client-level entities (no integration)."""
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, quote=False, name="tenant_id")
    active = Column(Boolean, nullable=False, default=True, quote=False, name="active")
    created_at = Column(DateTime, quote=False, name="created_at", default=func.now())
    last_updated_at = Column(DateTime, quote=False, name="last_updated_at", default=func.now())


class IntegrationBaseEntity:
    """Base class with audit fields for integration-specific entities."""
    integration_id = Column(Integer, ForeignKey('integrations.id'), nullable=False, quote=False, name="integration_id")
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, quote=False, name="tenant_id")
    active = Column(Boolean, nullable=False, default=True, quote=False, name="active")
    created_at = Column(DateTime, quote=False, name="created_at", default=func.now())
    last_updated_at = Column(DateTime, quote=False, name="last_updated_at", default=func.now())


# Authentication and User Management Tables
# These tables inherit from BaseEntity and are tied to specific clients

class User(Base, BaseEntity):
    """Users table for authentication and authorization."""
    __tablename__ = 'users'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    email = Column(String(255), unique=True, nullable=False, quote=False, name="email")
    first_name = Column(String(100), quote=False, name="first_name")
    last_name = Column(String(100), quote=False, name="last_name")
    role = Column(String(50), nullable=False, default='user', quote=False, name="role")  # 'admin', 'user', 'viewer'
    is_admin = Column(Boolean, default=False, quote=False, name="is_admin")

    # Authentication fields
    auth_provider = Column(String(50), nullable=False, default='local', quote=False, name="auth_provider")  # 'local', 'okta'
    okta_user_id = Column(String(255), unique=True, quote=False, name="okta_user_id")  # OKTA's user ID
    password_hash = Column(String(255), quote=False, name="password_hash")  # Only for local auth
    theme_mode = Column(String(10), nullable=False, default='light', quote=False, name="theme_mode")  # 'light', 'dark'

    # === ACCESSIBILITY PREFERENCES (moved from accessibility colors table) ===
    high_contrast_mode = Column(Boolean, default=False, quote=False, name="high_contrast_mode")
    reduce_motion = Column(Boolean, default=False, quote=False, name="reduce_motion")
    colorblind_safe_palette = Column(Boolean, default=False, quote=False, name="colorblind_safe_palette")
    accessibility_level = Column(String(10), default='regular', quote=False, name="accessibility_level")  # 'regular', 'AA', 'AAA'

    # Profile image fields
    profile_image_filename = Column(String(255), quote=False, name="profile_image_filename")  # Image filename

    # Metadata
    last_login_at = Column(DateTime, quote=False, name="last_login_at")



    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self, include_ml_fields: bool = False):
        """Convert User object to dictionary for API responses (Phase 3-1 clean)."""
        user_dict = {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role": self.role,
            "is_admin": self.is_admin,
            "auth_provider": self.auth_provider,
            "theme_mode": self.theme_mode,
            "high_contrast_mode": self.high_contrast_mode,
            "reduce_motion": self.reduce_motion,
            "colorblind_safe_palette": self.colorblind_safe_palette,
            "accessibility_level": self.accessibility_level,
            "profile_image_filename": self.profile_image_filename,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at is not None else None,
            "tenant_id": self.tenant_id,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None
        }

        # Note: In Phase 3-1, ML fields are not implemented yet
        # The include_ml_fields parameter is accepted for compatibility but ignored
        if include_ml_fields:
            # Future: Add ML fields here when implemented
            pass

        return user_dict


class UserSession(Base, BaseEntity):
    """User sessions table for JWT management."""
    __tablename__ = 'users_sessions'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, quote=False, name="user_id")
    token_hash = Column(String(255), nullable=False, quote=False, name="token_hash")  # Hashed JWT for revocation
    expires_at = Column(DateTime, nullable=False, quote=False, name="expires_at")
    ip_address = Column(String(45), quote=False, name="ip_address")  # IPv6 compatible
    user_agent = Column(Text, quote=False, name="user_agent")

    # Relationships
    user = relationship("User", back_populates="sessions")


class UserPermission(Base, BaseEntity):
    """User permissions table for fine-grained access control."""
    __tablename__ = 'users_permissions'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, quote=False, name="user_id")
    resource = Column(String(100), nullable=False, quote=False, name="resource")  # 'etl_jobs', 'dashboards', 'settings'
    action = Column(String(50), nullable=False, quote=False, name="action")  # 'read', 'execute', 'delete', 'admin'
    granted = Column(Boolean, nullable=False, default=True, quote=False, name="granted")  # True = grant, False = deny

    # Relationships
    user = relationship("User", back_populates="permissions")




class Integration(Base, BaseEntity):
    """Clean integrations table with unified settings architecture"""
    __tablename__ = 'integrations'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Core integration fields
    provider = Column(String(50), nullable=False, quote=False, name="provider")  # 'Jira', 'GitHub', 'WEX AI Gateway', etc.
    type = Column(String(50), nullable=False, name="type")  # 'Data', 'AI', 'Embedding', 'System'
    username = Column(String, name="username")
    password = Column(String, name="password")  # Encrypted tokens/passwords
    base_url = Column(Text, name="base_url")

    # Unified settings JSON for all integration-specific configuration
    settings = Column(JSON, default={}, name="settings")  # Type-specific settings (projects, models, costs, etc.)

    fallback_integration_id = Column(Integer, quote=False, name="fallback_integration_id")  # FK to another integration for fallback
    logo_filename = Column(String(255), quote=False, name="logo_filename")  # Filename of integration logo (stored in tenant assets folder)
    custom_field_mappings = Column(JSON, default={}, name="custom_field_mappings")  # Custom field mappings for Jira integrations

    # Relationships
    tenant = relationship("Tenant", back_populates="integrations")
    project_objects = relationship("Project", back_populates="integration")
    wits = relationship("Wit", back_populates="integration")
    statuses = relationship("Status", back_populates="integration")
    work_items = relationship("WorkItem", back_populates="integration")
    changelogs = relationship("Changelog", back_populates="integration")
    custom_fields = relationship("CustomField", back_populates="integration")
    custom_field_mappings = relationship("CustomFieldMapping", back_populates="integration")
    workflows = relationship("Workflow", back_populates="integration")
    repositories = relationship("Repository", back_populates="integration")
    prs = relationship("Pr", back_populates="integration")
    prs_reviews = relationship("PrReview", back_populates="integration")
    prs_commits = relationship("PrCommit", back_populates="integration")
    prs_comments = relationship("PrComment", back_populates="integration")
    work_items_prs_links = relationship("WorkItemPrLink", back_populates="integration")
    etl_jobs = relationship("JobSchedule", back_populates="integration")
    statuses_mappings = relationship("StatusMapping", back_populates="integration")
    wits_hierarchies = relationship("WitHierarchy", back_populates="integration")
    wits_mappings = relationship("WitMapping", back_populates="integration")

    # Phase 2.1: Issue types discovery relationships
    projects_issue_types = relationship("ProjectIssueType", back_populates="integration")

    # Phase 1: Raw extraction data relationships
    raw_extraction_data = relationship("RawExtractionData", back_populates="integration")
    custom_fields = relationship("CustomField", back_populates="integration")

class Project(Base, IntegrationBaseEntity):
    """Projects table"""
    __tablename__ = 'projects'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    key = Column(String, quote=False, unique=True, nullable=False, name="key")
    name = Column(String, quote=False, nullable=False, name="name")
    project_type = Column(String, quote=False, name="project_type")

    # Relationships
    tenant = relationship("Tenant", back_populates="projects")
    integration = relationship("Integration", back_populates="project_objects")
    wits = relationship("Wit", secondary="projects_wits", back_populates="projects")
    statuses = relationship("Status", secondary="projects_statuses", back_populates="projects")
    work_items = relationship("WorkItem", back_populates="project")
    issue_types = relationship("ProjectIssueType", back_populates="project")

class ProjectWits(Base):
    """Relationship table between projects and work item types"""
    __tablename__ = 'projects_wits'
    __table_args__ = (PrimaryKeyConstraint('project_id', 'wit_id'), {'quote': False})

    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True, quote=False, name="project_id")
    wit_id = Column(Integer, ForeignKey('wits.id'), primary_key=True, quote=False, name="wit_id")

class ProjectsStatuses(Base):
    """Relationship table between projects and statuses"""
    __tablename__ = 'projects_statuses'
    __table_args__ = (PrimaryKeyConstraint('project_id', 'status_id'), {'quote': False})

    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True, quote=False, name="project_id")
    status_id = Column(Integer, ForeignKey('statuses.id'), primary_key=True, quote=False, name="status_id")

class CustomField(Base, IntegrationBaseEntity):
    """Custom fields table - stores global Jira custom field definitions"""
    __tablename__ = 'custom_fields'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'integration_id', 'external_id', name='uk_custom_fields_external_id'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # === CUSTOM FIELD IDENTIFIERS ===
    external_id = Column(String(100), nullable=False, quote=False, name="external_id")  # Jira field key like "customfield_10150", "customfield_10128"
    name = Column(String(255), nullable=False, quote=False, name="name")  # Human-readable name like "Aha! Initiative", "Agile Team"

    # === FIELD SCHEMA ===
    field_type = Column(String(100), nullable=False, quote=False, name="field_type")  # Schema type like "string", "option", "array", "number", "date", "team"

    # === FIELD OPERATIONS ===
    operations = Column(JSON, default=list, quote=False, name="operations")  # Array of allowed operations like ["set"], ["add", "set", "remove"]

    # Relationships
    tenant = relationship("Tenant", back_populates="custom_fields")
    integration = relationship("Integration", back_populates="custom_fields")


class CustomFieldMapping(Base, IntegrationBaseEntity):
    """Custom fields mapping table - stores direct mapping to 20 work item columns"""
    __tablename__ = 'custom_fields_mapping'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'integration_id', name='uk_custom_fields_mapping_integration'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # === 20 CUSTOM FIELD MAPPINGS ===
    custom_field_01_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_01_id")
    custom_field_02_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_02_id")
    custom_field_03_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_03_id")
    custom_field_04_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_04_id")
    custom_field_05_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_05_id")
    custom_field_06_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_06_id")
    custom_field_07_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_07_id")
    custom_field_08_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_08_id")
    custom_field_09_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_09_id")
    custom_field_10_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_10_id")
    custom_field_11_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_11_id")
    custom_field_12_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_12_id")
    custom_field_13_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_13_id")
    custom_field_14_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_14_id")
    custom_field_15_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_15_id")
    custom_field_16_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_16_id")
    custom_field_17_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_17_id")
    custom_field_18_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_18_id")
    custom_field_19_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_19_id")
    custom_field_20_id = Column(Integer, ForeignKey('custom_fields.id'), quote=False, name="custom_field_20_id")

    # Relationships
    tenant = relationship("Tenant", back_populates="custom_field_mappings")
    integration = relationship("Integration", back_populates="custom_field_mappings")

    # Relationships to custom fields
    custom_field_01 = relationship("CustomField", foreign_keys=[custom_field_01_id])
    custom_field_02 = relationship("CustomField", foreign_keys=[custom_field_02_id])
    custom_field_03 = relationship("CustomField", foreign_keys=[custom_field_03_id])
    custom_field_04 = relationship("CustomField", foreign_keys=[custom_field_04_id])
    custom_field_05 = relationship("CustomField", foreign_keys=[custom_field_05_id])
    custom_field_06 = relationship("CustomField", foreign_keys=[custom_field_06_id])
    custom_field_07 = relationship("CustomField", foreign_keys=[custom_field_07_id])
    custom_field_08 = relationship("CustomField", foreign_keys=[custom_field_08_id])
    custom_field_09 = relationship("CustomField", foreign_keys=[custom_field_09_id])
    custom_field_10 = relationship("CustomField", foreign_keys=[custom_field_10_id])
    custom_field_11 = relationship("CustomField", foreign_keys=[custom_field_11_id])
    custom_field_12 = relationship("CustomField", foreign_keys=[custom_field_12_id])
    custom_field_13 = relationship("CustomField", foreign_keys=[custom_field_13_id])
    custom_field_14 = relationship("CustomField", foreign_keys=[custom_field_14_id])
    custom_field_15 = relationship("CustomField", foreign_keys=[custom_field_15_id])
    custom_field_16 = relationship("CustomField", foreign_keys=[custom_field_16_id])
    custom_field_17 = relationship("CustomField", foreign_keys=[custom_field_17_id])
    custom_field_18 = relationship("CustomField", foreign_keys=[custom_field_18_id])
    custom_field_19 = relationship("CustomField", foreign_keys=[custom_field_19_id])
    custom_field_20 = relationship("CustomField", foreign_keys=[custom_field_20_id])


class Wit(Base, IntegrationBaseEntity):
    """Work item types table"""
    __tablename__ = 'wits'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    original_name = Column(String, quote=False, nullable=False, name="original_name")
    wit_mapping_id = Column(Integer, ForeignKey('wits_mappings.id'), quote=False, nullable=True, name="wits_mapping_id")
    description = Column(String, quote=False, name="description")
    hierarchy_level = Column(Integer, quote=False, nullable=False, name="hierarchy_level")

    # Relationships
    tenant = relationship("Tenant", back_populates="wits")
    integration = relationship("Integration", back_populates="wits")
    projects = relationship("Project", secondary="projects_wits", back_populates="wits")
    wits_mappings = relationship("WitMapping", back_populates="wit")
    work_items = relationship("WorkItem", back_populates="wit")

class StatusMapping(Base, IntegrationBaseEntity):
    """Status Mapping table - maps raw status names to standardized flow steps"""
    __tablename__ = 'statuses_mappings'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    status_from = Column(String, quote=False, nullable=False, name="status_from")
    status_to = Column(String, quote=False, nullable=False, name="status_to")
    status_category = Column(String, quote=False, nullable=False, name="status_category")
    workflow_id = Column(Integer, ForeignKey('workflows.id'), quote=False, nullable=True, name="workflow_id")

    # Relationships
    tenant = relationship("Tenant", back_populates="statuses_mappings")
    integration = relationship("Integration", back_populates="statuses_mappings")
    workflow = relationship("Workflow", back_populates="statuses_mappings")

class WitHierarchy(Base, IntegrationBaseEntity):
    """WorkItem Type Hierarchies table - defines hierarchy levels and their properties"""
    __tablename__ = 'wits_hierarchies'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    level_name = Column(String, quote=False, nullable=False, name="level_name")
    level_number = Column(Integer, quote=False, nullable=False, name="level_number")
    description = Column(String, quote=False, nullable=True, name="description")

    # Relationships
    tenant = relationship("Tenant", back_populates="wits_hierarchies")
    integration = relationship("Integration", back_populates="wits_hierarchies")
    wits_mappings = relationship("WitMapping", back_populates="wit_hierarchy")


class WitMapping(Base, IntegrationBaseEntity):
    """WorkItem Type Mapping table - maps raw issue type names to standardized work item types"""
    __tablename__ = 'wits_mappings'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    wit_from = Column(String, quote=False, nullable=False, name="wit_from")
    wit_to = Column(String, quote=False, nullable=False, name="wit_to")
    wits_hierarchy_id = Column(Integer, ForeignKey('wits_hierarchies.id'), quote=False, nullable=False, name="wits_hierarchy_id")

    # Relationships
    tenant = relationship("Tenant", back_populates="wits_mappings")
    integration = relationship("Integration", back_populates="wits_mappings")
    wit = relationship("Wit", back_populates="wits_mappings")
    wit_hierarchy = relationship("WitHierarchy", back_populates="wits_mappings")

class Workflow(Base, IntegrationBaseEntity):
    """Workflows table - client and integration-specific workflow steps"""
    __tablename__ = 'workflows'
    __table_args__ = (
        # Ensure only one commitment point per client/integration combination
        Index('idx_unique_commitment_point_per_client_integration', 'tenant_id', 'integration_id',
              postgresql_where=text('is_commitment_point = true')),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    step_name = Column(String, quote=False, nullable=False, name="step_name")  # Renamed from name
    step_number = Column(Integer, quote=False, nullable=True, name="step_number")
    step_category = Column(String, quote=False, nullable=False, name="step_category")
    is_commitment_point = Column(Boolean, quote=False, nullable=False, default=False, name="is_commitment_point")  # Commitment point for lead time calculation

    # Relationships
    tenant = relationship("Tenant", back_populates="workflows")
    integration = relationship("Integration", back_populates="workflows")
    statuses_mappings = relationship("StatusMapping", back_populates="workflow")

class Status(Base, IntegrationBaseEntity):
    """Statuses table"""
    __tablename__ = 'statuses'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    original_name = Column(String, quote=False, nullable=False, name="original_name")
    status_mapping_id = Column(Integer, ForeignKey('status_mappings.id'), quote=False, nullable=True, name="status_mapping_id")
    category = Column(String, quote=False, nullable=False, name="category")
    description = Column(String, quote=False, name="description")

    # Relationships
    tenant = relationship("Tenant", back_populates="statuses")
    integration = relationship("Integration", back_populates="statuses")
    projects = relationship("Project", secondary="projects_statuses", back_populates="statuses")
    work_items = relationship("WorkItem", back_populates="status")

class WorkItem(Base, IntegrationBaseEntity):
    """Main issues table"""
    __tablename__ = 'work_items'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    key = Column(String, quote=False, name="key")
    project_id = Column(Integer, ForeignKey('projects.id'), quote=False, name="project_id")
    team = Column(String, quote=False, name="team")
    summary = Column(String, quote=False, name="summary")
    description = Column(Text, quote=False, name="description")
    acceptance_criteria = Column(Text, quote=False, name="acceptance_criteria")
    wit_id = Column(Integer, ForeignKey('wits.id'), quote=False, name="wit_id")
    status_id = Column(Integer, ForeignKey('statuses.id'), quote=False, name="status_id")
    resolution = Column(String, quote=False, name="resolution")
    story_points = Column(Integer, quote=False, name="story_points")
    assignee = Column(String, quote=False, name="assignee")
    labels = Column(String, quote=False, name="labels")
    created = Column(DateTime, quote=False, name="created")
    updated = Column(DateTime, quote=False, name="updated")

    # Enhanced workflow timing columns
    work_first_committed_at = Column(DateTime, quote=False, name="work_first_committed_at")
    work_first_started_at = Column(DateTime, quote=False, name="work_first_started_at")
    work_last_started_at = Column(DateTime, quote=False, name="work_last_started_at")
    work_first_completed_at = Column(DateTime, quote=False, name="work_first_completed_at")
    work_last_completed_at = Column(DateTime, quote=False, name="work_last_completed_at")
    priority = Column(String, quote=False, name="priority")
    parent_external_id = Column(String, quote=False, name="parent_external_id")  # Changed to external_id reference
    code_changed = Column(Boolean, quote=False, name="code_changed")

    # Enhanced workflow counter columns
    total_work_starts = Column(Integer, quote=False, name="total_work_starts", default=0)
    total_completions = Column(Integer, quote=False, name="total_completions", default=0)
    total_backlog_returns = Column(Integer, quote=False, name="total_backlog_returns", default=0)

    # Enhanced workflow time analysis columns
    total_work_time_seconds = Column(Float, quote=False, name="total_work_time_seconds", default=0.0)
    total_review_time_seconds = Column(Float, quote=False, name="total_review_time_seconds", default=0.0)
    total_cycle_time_seconds = Column(Float, quote=False, name="total_cycle_time_seconds", default=0.0)
    total_lead_time_seconds = Column(Float, quote=False, name="total_lead_time_seconds", default=0.0)

    # Enhanced workflow pattern analysis columns
    workflow_complexity_score = Column(Integer, quote=False, name="workflow_complexity_score", default=0)
    rework_indicator = Column(Boolean, quote=False, name="rework_indicator", default=False)
    direct_completion = Column(Boolean, quote=False, name="direct_completion", default=False)

    # Custom fields for flexible data storage
    custom_field_01 = Column(String, quote=False, name="custom_field_01")
    custom_field_02 = Column(String, quote=False, name="custom_field_02")
    custom_field_03 = Column(String, quote=False, name="custom_field_03")
    custom_field_04 = Column(String, quote=False, name="custom_field_04")
    custom_field_05 = Column(String, quote=False, name="custom_field_05")
    custom_field_06 = Column(String, quote=False, name="custom_field_06")
    custom_field_07 = Column(String, quote=False, name="custom_field_07")
    custom_field_08 = Column(String, quote=False, name="custom_field_08")
    custom_field_09 = Column(String, quote=False, name="custom_field_09")
    custom_field_10 = Column(String, quote=False, name="custom_field_10")
    custom_field_11 = Column(String, quote=False, name="custom_field_11")
    custom_field_12 = Column(String, quote=False, name="custom_field_12")
    custom_field_13 = Column(String, quote=False, name="custom_field_13")
    custom_field_14 = Column(String, quote=False, name="custom_field_14")
    custom_field_15 = Column(String, quote=False, name="custom_field_15")
    custom_field_16 = Column(String, quote=False, name="custom_field_16")
    custom_field_17 = Column(String, quote=False, name="custom_field_17")
    custom_field_18 = Column(String, quote=False, name="custom_field_18")
    custom_field_19 = Column(String, quote=False, name="custom_field_19")
    custom_field_20 = Column(String, quote=False, name="custom_field_20")
    custom_fields_overflow = Column(JSON, quote=False, name="custom_fields_overflow")

    # Relationships
    tenant = relationship("Tenant", back_populates="work_items")
    project = relationship("Project", back_populates="work_items")
    wit = relationship("Wit", back_populates="work_items")
    status = relationship("Status", back_populates="work_items")
    integration = relationship("Integration", back_populates="work_items")



    # Note: Parent-child relationships now use external_id instead of foreign key
    # This provides better data integrity and simpler import logic

    # New relationships for development data
    prs = relationship("Pr", back_populates="work_item")
    changelogs = relationship("Changelog", back_populates="work_item")
    pr_links = relationship("WorkItemPrLink", back_populates="work_item")

class Changelog(Base, IntegrationBaseEntity):
    """Work item status change history table"""
    __tablename__ = 'changelogs'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    work_item_id = Column(Integer, ForeignKey('work_items.id'), quote=False, nullable=False, name="work_item_id")
    external_id = Column(String, quote=False, name="external_id")  # e.g., "BEX-123-456"

    # Status transition information
    from_status_id = Column(Integer, ForeignKey('statuses.id'), quote=False, name="from_status_id")
    to_status_id = Column(Integer, ForeignKey('statuses.id'), quote=False, name="to_status_id")

    # Timing information
    transition_start_date = Column(DateTime, quote=False, name="transition_start_date")
    transition_change_date = Column(DateTime, quote=False, name="transition_change_date")
    time_in_status_seconds = Column(Float, quote=False, name="time_in_status_seconds")

    # Change metadata
    changed_by = Column(String, quote=False, name="changed_by")

    # Relationships
    tenant = relationship("Tenant", back_populates="changelogs")
    integration = relationship("Integration", back_populates="changelogs")
    work_item = relationship("WorkItem", back_populates="changelogs")
    from_status = relationship("Status", foreign_keys=[from_status_id])
    to_status = relationship("Status", foreign_keys=[to_status_id])

class Repository(Base, IntegrationBaseEntity):
    """Repositories table"""
    __tablename__ = 'repositories'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    name = Column(String, quote=False, name="name")
    full_name = Column(String, quote=False, name="full_name")
    description = Column(Text, quote=False, name="description")
    url = Column(String, quote=False, name="url")
    is_private = Column(Boolean, quote=False, name="is_private")
    repo_created_at = Column(DateTime, quote=False, name="repo_created_at")
    repo_updated_at = Column(DateTime, quote=False, name="repo_updated_at")
    pushed_at = Column(DateTime, quote=False, name="pushed_at")
    language = Column(String, quote=False, name="language")
    default_branch = Column(String, quote=False, name="default_branch")
    archived = Column(Boolean, quote=False, name="archived")

    # Relationships
    tenant = relationship("Tenant", back_populates="repositories")
    integration = relationship("Integration", back_populates="repositories")
    prs = relationship("Pr", back_populates="repository")

class Pr(Base, IntegrationBaseEntity):
    """PRs table - can be updated by both Jira and GitHub integrations"""
    __tablename__ = 'prs'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    external_repo_id = Column(String, quote=False, name="external_repo_id")  # GitHub repository ID for linking
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False, quote=False, name="repository_id")
    work_item_id = Column(Integer, ForeignKey('work_items.id'), nullable=True, quote=False, name="work_item_id")
    number = Column(Integer, quote=False, name="number")
    name = Column(String, quote=False, name="name")
    user_name = Column(String, quote=False, name="user_name")
    body = Column(Text, quote=False, name="body")
    discussion_comment_count = Column(Integer, quote=False, name="discussion_comment_count")
    review_comment_count = Column(Integer, quote=False, name="review_comment_count")
    source = Column(String, quote=False, name="source")
    destination = Column(String, quote=False, name="destination")
    reviewers = Column(Integer, quote=False, name="reviewers")
    status = Column(String, quote=False, name="status")
    url = Column(String, quote=False, name="url")
    pr_created_at = Column(DateTime, quote=False, name="pr_created_at")
    pr_updated_at = Column(DateTime, quote=False, name="pr_updated_at")
    closed_at = Column(DateTime, quote=False, name="closed_at")
    merged_at = Column(DateTime, quote=False, name="merged_at")
    merged_by = Column(String, quote=False, name="merged_by")
    commit_count = Column(Integer, quote=False, name="commit_count")
    additions = Column(Integer, quote=False, name="additions")
    deletions = Column(Integer, quote=False, name="deletions")
    changed_files = Column(Integer, quote=False, name="changed_files")
    first_review_at = Column(DateTime, quote=False, name="first_review_at")
    rework_commit_count = Column(Integer, quote=False, name="rework_commit_count")
    review_cycles = Column(Integer, quote=False, name="review_cycles")

    # Relationships
    repository = relationship("Repository", back_populates="prs")
    work_item = relationship("WorkItem", back_populates="prs")
    tenant = relationship("Tenant", back_populates="prs")
    integration = relationship("Integration", back_populates="prs")

    # New relationships for detailed PR conversation tracking
    reviews = relationship("PrReview", back_populates="pr")
    commits = relationship("PrCommit", back_populates="pr")
    comments = relationship("PrComment", back_populates="pr")

class PrReview(Base, IntegrationBaseEntity):
    """Pull Request Reviews table - stores each formal review submission"""
    __tablename__ = 'prs_reviews'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")  # GitHub review ID
    pr_id = Column(Integer, ForeignKey('prs.id'), nullable=False, quote=False, name="pull_request_id")
    author_login = Column(String, quote=False, name="author_login")  # Reviewer's GitHub username
    state = Column(String, quote=False, name="state")  # APPROVED, CHANGES_REQUESTED, COMMENTED
    body = Column(Text, quote=False, name="body")  # Review comment text
    submitted_at = Column(DateTime, quote=False, name="submitted_at")  # Review submission timestamp

    # Relationships
    pr = relationship("Pr", back_populates="reviews")
    tenant = relationship("Tenant", back_populates="prs_reviews")
    integration = relationship("Integration", back_populates="prs_reviews")

class PrCommit(Base, IntegrationBaseEntity):
    """Pull Request Commits table - stores each individual commit associated with a PR"""
    __tablename__ = 'prs_commits'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")  # SHA, the commit hash
    pr_id = Column(Integer, ForeignKey('prs.id'), nullable=False, quote=False, name="pull_request_id")
    author_name = Column(String, quote=False, name="author_name")  # Commit author name
    author_email = Column(String, quote=False, name="author_email")  # Commit author email
    committer_name = Column(String, quote=False, name="committer_name")  # Committer name
    committer_email = Column(String, quote=False, name="committer_email")  # Committer email
    message = Column(Text, quote=False, name="message")  # Commit message
    authored_date = Column(DateTime, quote=False, name="authored_date")  # Commit timestamp
    committed_date = Column(DateTime, quote=False, name="committed_date")  # Committed timestamp

    # Relationships
    pr = relationship("Pr", back_populates="commits")
    tenant = relationship("Tenant", back_populates="prs_commits")
    integration = relationship("Integration", back_populates="prs_commits")

class PrComment(Base, IntegrationBaseEntity):
    """Pull Request Comments table - stores all comments made on the PR's main thread and on specific lines of code"""
    __tablename__ = 'prs_comments'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")  # GitHub comment ID
    pr_id = Column(Integer, ForeignKey('prs.id'), nullable=False, quote=False, name="pull_request_id")
    author_login = Column(String, quote=False, name="author_login")  # Comment author's GitHub username
    body = Column(Text, quote=False, name="body")  # Comment text
    comment_type = Column(String, quote=False, name="comment_type")  # 'issue' (main thread) or 'review' (line-specific)
    path = Column(String, quote=False, name="path")  # File path for line-specific comments
    position = Column(Integer, quote=False, name="position")  # Line position for line-specific comments
    line = Column(Integer, quote=False, name="line")  # Line number for line-specific comments
    created_at_github = Column(DateTime, quote=False, name="created_at_github")  # GitHub timestamp
    updated_at_github = Column(DateTime, quote=False, name="updated_at_github")  # GitHub update timestamp

    # Relationships
    pr = relationship("Pr", back_populates="comments")
    tenant = relationship("Tenant", back_populates="prs_comments")
    integration = relationship("Integration", back_populates="prs_comments")

class SystemSettings(Base, BaseEntity):
    """
    System-wide configuration settings stored in database.

    This table stores configurable system settings that can be modified
    through the UI without requiring code changes or server restarts.
    """

    __tablename__ = 'system_settings'
    __table_args__ = {'quote': False}

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Setting identification
    setting_key = Column(String, unique=True, nullable=False, quote=False, name="setting_key")
    setting_value = Column(String, nullable=False, quote=False, name="setting_value")
    setting_type = Column(String, nullable=False, default='string', quote=False, name="setting_type")  # 'string', 'integer', 'boolean', 'json'
    description = Column(String, nullable=True, quote=False, name="description")

    # Relationships
    tenant = relationship("Tenant", back_populates="system_settings")

    def get_typed_value(self):
        """Returns the setting value converted to its proper type."""
        if self.setting_type == 'integer':  # type: ignore
            return int(self.setting_value)  # type: ignore
        elif self.setting_type == 'boolean':  # type: ignore
            return self.setting_value.lower() in ('true', '1', 'yes', 'on')  # type: ignore
        elif self.setting_type == 'json':  # type: ignore
            import json
            return json.loads(self.setting_value)  # type: ignore
        else:
            return self.setting_value

    def set_typed_value(self, value):
        """Sets the setting value from a typed value."""
        if self.setting_type == 'integer':  # type: ignore
            self.setting_value = str(int(value))
        elif self.setting_type == 'boolean':  # type: ignore
            self.setting_value = str(bool(value)).lower()
        elif self.setting_type == 'json':  # type: ignore
            import json
            self.setting_value = json.dumps(value)
        else:
            self.setting_value = str(value)


class JobSchedule(Base, IntegrationBaseEntity):
    """
    ETL Job Management with Independent Scheduling.

    Each job runs independently with its own schedule and timing.
    No orchestrator dependency - jobs are autonomous.
    """

    __tablename__ = 'etl_jobs'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Job identification and configuration
    job_name = Column(String, nullable=False, quote=False, name="job_name")  # 'Jira', 'GitHub', 'WEX AD', 'WEX Fabric'
    status = Column(String, nullable=False, default='READY', quote=False, name="status")  # 'READY', 'RUNNING', 'FINISHED', 'FAILED'

    # Scheduling configuration
    schedule_interval_minutes = Column(Integer, nullable=False, default=360, quote=False, name="schedule_interval_minutes")  # Normal interval
    retry_interval_minutes = Column(Integer, nullable=False, default=15, quote=False, name="retry_interval_minutes")  # Retry interval
    next_run = Column(DateTime, nullable=True, quote=False, name="next_run")  # When job should run next

    # Execution tracking
    last_run_started_at = Column(DateTime, nullable=True, quote=False, name="last_run_started_at")
    last_run_finished_at = Column(DateTime, nullable=True, quote=False, name="last_run_finished_at")
    error_message = Column(Text, nullable=True, quote=False, name="error_message")
    retry_count = Column(Integer, default=0, quote=False, name="retry_count")

    # Checkpoint data for recovery
    checkpoint_data = Column(Text, nullable=True, quote=False, name="checkpoint_data")  # JSONB stored as text

    # Relationships
    integration = relationship("Integration", back_populates="etl_jobs")

    def clear_checkpoints(self):
        """Clear checkpoint data after successful completion."""
        self.checkpoint_data = None
        self.error_message = None
        self.retry_count = 0

    def has_recovery_checkpoints(self) -> bool:
        """Check if there are recovery checkpoints available."""
        return self.checkpoint_data is not None

    def set_running(self):
        """Mark job as running and update timing."""
        from app.core.utils import DateTimeHelper
        self.status = 'RUNNING'
        self.last_run_started_at = DateTimeHelper.now_default()

    def set_finished(self):
        """Mark job as finished and calculate next run time."""
        from app.core.utils import DateTimeHelper
        from datetime import timedelta

        now = DateTimeHelper.now_default()
        self.status = 'READY'  # Ready for next run
        self.last_run_finished_at = now
        self.clear_checkpoints()

        # Calculate next run time
        self.next_run = now + timedelta(minutes=self.schedule_interval_minutes)

    def set_failed(self, error_message: str):
        """Mark job as failed and calculate retry time."""
        from app.core.utils import DateTimeHelper
        from datetime import timedelta

        now = DateTimeHelper.now_default()
        self.status = 'FAILED'
        self.error_message = error_message
        self.retry_count += 1

        # Calculate next retry time
        self.next_run = now + timedelta(minutes=self.retry_interval_minutes)

    def calculate_next_run(self):
        """Calculate when this job should run next based on current state."""
        from app.core.utils import DateTimeHelper
        from datetime import timedelta

        now = DateTimeHelper.now_default()

        if self.status == 'FAILED':
            # Use retry interval for failed jobs
            self.next_run = now + timedelta(minutes=self.retry_interval_minutes)
        else:
            # Use normal schedule interval
            self.next_run = now + timedelta(minutes=self.schedule_interval_minutes)

        return self.next_run

    def is_ready_to_run(self) -> bool:
        """Check if job is ready to run based on status and timing."""
        if not self.active:
            return False
        if self.status == 'RUNNING':
            return False
        if self.next_run is None:
            return True  # Never run before, ready to start

        from app.core.utils import DateTimeHelper
        now = DateTimeHelper.now_default()
        return now >= self.next_run

    def set_paused(self):
        """Mark job as paused."""
        self.status = 'PAUSED'

    def set_unpaused(self, other_job_status: str):
        """
        Mark job as unpaused with logic based on other job status.

        Args:
            other_job_status: Status of the other job ('PENDING', 'RUNNING', 'FINISHED', 'PAUSED')
        """
        if other_job_status in ['PENDING', 'RUNNING']:
            self.status = 'FINISHED'
        else:  # other job is 'FINISHED' or 'PAUSED'
            self.status = 'PENDING'

    def set_pending_with_checkpoint(self, error_message: str, repo_checkpoint: Optional[datetime] = None,
                                   repo_queue: Optional[List[Any]] = None, last_pr_cursor: Optional[str] = None,
                                   current_pr_node_id: Optional[str] = None, last_commit_cursor: Optional[str] = None,
                                   last_review_cursor: Optional[str] = None, last_comment_cursor: Optional[str] = None,
                                   last_review_thread_cursor: Optional[str] = None):
        """Mark job as pending with checkpoint data for recovery."""
        self.status = 'PENDING'
        self.error_message = error_message
        self.retry_count += 1
        if repo_checkpoint:
            self.last_repo_sync_checkpoint = repo_checkpoint
        if repo_queue is not None:
            import json
            self.repo_processing_queue = json.dumps(repo_queue)
        if last_pr_cursor:
            self.last_pr_cursor = last_pr_cursor
        if current_pr_node_id:
            self.current_pr_node_id = current_pr_node_id
        if last_commit_cursor:
            self.last_commit_cursor = last_commit_cursor
        if last_review_cursor:
            self.last_review_cursor = last_review_cursor
        if last_comment_cursor:
            self.last_comment_cursor = last_comment_cursor
        if last_review_thread_cursor:
            self.last_review_thread_cursor = last_review_thread_cursor

    def is_recovery_run(self) -> bool:
        """Check if this is a recovery run (has repo queue or cursor checkpoints)."""
        return self.repo_processing_queue is not None or self.last_pr_cursor is not None



    def get_checkpoint_state(self) -> Dict[str, Any]:
        """Get current checkpoint state for recovery."""
        repo_queue = None
        if self.repo_processing_queue:  # type: ignore
            import json
            repo_queue = json.loads(self.repo_processing_queue)  # type: ignore

        return {
            'repo_processing_queue': repo_queue,
            'last_pr_cursor': self.last_pr_cursor,
            'current_pr_node_id': self.current_pr_node_id,
            'last_commit_cursor': self.last_commit_cursor,
            'last_review_cursor': self.last_review_cursor,
            'last_comment_cursor': self.last_comment_cursor,
            'last_review_thread_cursor': self.last_review_thread_cursor
        }

    def update_checkpoint(self, checkpoint_data: Dict[str, Any]):
        """Update checkpoint data for recovery."""
        if 'repo_processing_queue' in checkpoint_data:
            import json
            self.repo_processing_queue = json.dumps(checkpoint_data['repo_processing_queue'])
        if 'last_pr_cursor' in checkpoint_data:
            self.last_pr_cursor = checkpoint_data['last_pr_cursor']
        if 'current_pr_node_id' in checkpoint_data:
            self.current_pr_node_id = checkpoint_data['current_pr_node_id']
        if 'last_commit_cursor' in checkpoint_data:
            self.last_commit_cursor = checkpoint_data['last_commit_cursor']
        if 'last_review_cursor' in checkpoint_data:
            self.last_review_cursor = checkpoint_data['last_review_cursor']
        if 'last_comment_cursor' in checkpoint_data:
            self.last_comment_cursor = checkpoint_data['last_comment_cursor']
        if 'last_review_thread_cursor' in checkpoint_data:
            self.last_review_thread_cursor = checkpoint_data['last_review_thread_cursor']

    def initialize_repo_queue(self, repositories):
        """Initialize processing queue for normal run."""
        import json
        queue = [
            {
                "repo_id": repo.external_id,
                "full_name": repo.full_name,
                "finished": False
            }
            for repo in repositories
        ]
        self.repo_processing_queue = json.dumps(queue)

    def mark_repo_finished(self, repo_id: str):
        """Mark repository as completed in the queue."""
        if not self.repo_processing_queue:  # type: ignore
            return

        import json
        queue = json.loads(self.repo_processing_queue)  # type: ignore
        repo_found = False
        for repo in queue:
            if repo["repo_id"] == repo_id:
                repo["finished"] = True
                repo_found = True
                break

        if repo_found:
            self.repo_processing_queue = json.dumps(queue)
            # Mark the object as modified for SQLAlchemy
            from sqlalchemy.orm import object_session
            session = object_session(self)
            if session:
                session.add(self)  # Ensure SQLAlchemy tracks the change

            # Debug logging
            from app.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.debug(f"Marked repository {repo_id} as finished in queue")
        else:
            # Log warning if repo not found in queue
            from app.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Repository {repo_id} not found in processing queue")

    def cleanup_finished_repos(self):
        """Keep all repos in queue for analysis, just return remaining count."""
        if not self.repo_processing_queue:  # type: ignore
            return 0

        import json
        queue = json.loads(self.repo_processing_queue)  # type: ignore
        remaining_repos = [repo for repo in queue if not repo.get("finished", False)]

        if len(remaining_repos) == 0:
            # All repos finished - clear everything
            self.clear_checkpoints()
            return 0
        else:
            # Keep the full queue with finished=true entries for analysis
            # Just return count of remaining work
            return len(remaining_repos)

    def get_repo_queue(self):
        """Get the current repository queue (all entries for analysis)."""
        if not self.repo_processing_queue:  # type: ignore
            return []

        import json
        return json.loads(self.repo_processing_queue)  # type: ignore

    def get_unfinished_repos(self):
        """Get only unfinished repositories for recovery processing."""
        if not self.repo_processing_queue:  # type: ignore
            return []

        import json
        queue = json.loads(self.repo_processing_queue)  # type: ignore
        return [repo for repo in queue if not repo.get("finished", False)]


class WorkItemPrLink(Base, IntegrationBaseEntity):
    """
    Permanent table storing work item (Jira issue) to PR links from dev_status API.

    This table stores the facts about which PRs are linked to which work items,
    allowing for clean join-based queries without complex staging logic.
    """

    __tablename__ = 'work_items_prs_links'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Foreign keys
    work_item_id = Column(Integer, ForeignKey('work_items.id'), nullable=False, quote=False, name="work_item_id")

    # PR identification (for joining with pull_requests table)
    external_repo_id = Column(String, nullable=False, quote=False, name="external_repo_id")  # GitHub repo ID
    repo_full_name = Column(String, nullable=False, quote=False, name="repo_full_name")  # GitHub repo full name (e.g., "wexinc/health-api")
    pull_request_number = Column(Integer, nullable=False, quote=False, name="pull_request_number")

    # Metadata from dev_status API
    branch_name = Column(String, quote=False, name="branch_name")
    commit_sha = Column(String, quote=False, name="commit_sha")
    pr_status = Column(String, quote=False, name="pr_status")  # 'OPEN', 'MERGED', 'DECLINED'

    # Relationships
    work_item = relationship("WorkItem", back_populates="pr_links")
    tenant = relationship("Tenant", back_populates="work_items_prs_links")
    integration = relationship("Integration", back_populates="work_items_prs_links")

class MigrationHistory(Base):
    """Migration history tracking table for database migrations."""
    __tablename__ = 'migration_history'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    migration_number = Column(String(10), nullable=False, unique=True, quote=False, name="migration_number")
    migration_name = Column(String(255), nullable=False, quote=False, name="migration_name")
    applied_at = Column(DateTime, quote=False, name="applied_at", default=func.now())
    rollback_at = Column(DateTime, nullable=True, quote=False, name="rollback_at")
    status = Column(String(20), nullable=False, default='applied', quote=False, name="status")  # 'applied', 'rolled_back'


class DoraMarketBenchmark(Base):
    """Global quantitative benchmarks for DORA metrics by tier and year."""
    __tablename__ = 'dora_market_benchmarks'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    report_year = Column(Integer, nullable=False, quote=False, name="report_year")
    report_source = Column(String(100), nullable=True, default='Google DORA Report', quote=False, name="report_source")
    performance_tier = Column(String(20), nullable=False, quote=False, name="performance_tier")
    metric_name = Column(String(50), nullable=False, quote=False, name="metric_name")
    metric_value = Column(String(50), nullable=False, quote=False, name="metric_value")
    metric_unit = Column(String(20), nullable=True, quote=False, name="metric_unit")
    created_at = Column(DateTime, quote=False, name="created_at", server_default=func.now())


class DoraMetricInsight(Base):
    """Global qualitative insights for DORA metrics by year."""
    __tablename__ = 'dora_metric_insights'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    report_year = Column(Integer, nullable=False, quote=False, name="report_year")
    metric_name = Column(String(50), nullable=False, quote=False, name="metric_name")
    insight_text = Column(Text, nullable=False, quote=False, name="insight_text")
    created_at = Column(DateTime, quote=False, name="created_at", server_default=func.now())


# Color Management Tables
# These tables manage client-specific color schemas and accessibility variants

class TenantColors(Base, BaseEntity):
    """Unified color settings table with all color variants and accessibility levels."""
    __tablename__ = 'tenants_colors'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'color_schema_mode', 'accessibility_level', 'theme_mode'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # === IDENTIFIERS ===
    color_schema_mode = Column(String(10), nullable=False, quote=False, name="color_schema_mode")  # 'default' or 'custom'
    accessibility_level = Column(String(10), nullable=False, quote=False, name="accessibility_level")  # 'regular', 'AA', 'AAA'
    theme_mode = Column(String(5), nullable=False, quote=False, name="theme_mode")  # 'light' or 'dark'

    # === BASE COLORS (5 columns) ===
    color1 = Column(String(7), quote=False, name="color1")
    color2 = Column(String(7), quote=False, name="color2")
    color3 = Column(String(7), quote=False, name="color3")
    color4 = Column(String(7), quote=False, name="color4")
    color5 = Column(String(7), quote=False, name="color5")

    # === CALCULATED VARIANTS (10 columns) ===
    on_color1 = Column(String(7), quote=False, name="on_color1")
    on_color2 = Column(String(7), quote=False, name="on_color2")
    on_color3 = Column(String(7), quote=False, name="on_color3")
    on_color4 = Column(String(7), quote=False, name="on_color4")
    on_color5 = Column(String(7), quote=False, name="on_color5")
    on_gradient_1_2 = Column(String(7), quote=False, name="on_gradient_1_2")
    on_gradient_2_3 = Column(String(7), quote=False, name="on_gradient_2_3")
    on_gradient_3_4 = Column(String(7), quote=False, name="on_gradient_3_4")
    on_gradient_4_5 = Column(String(7), quote=False, name="on_gradient_4_5")
    on_gradient_5_1 = Column(String(7), quote=False, name="on_gradient_5_1")

    # Relationships
    tenant = relationship("Tenant", back_populates="color_settings")


# ===================================
# AI ENHANCEMENT: ML MONITORING MODELS
# ===================================

class AILearningMemory(Base, BaseEntity):
    """AI Learning Memories table - stores user feedback and corrections for ML improvement."""
    __tablename__ = 'ai_learning_memories'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    error_type = Column(String(50), nullable=False, quote=False, name="error_type")
    user_intent = Column(Text, nullable=False, quote=False, name="user_intent")
    failed_query = Column(Text, nullable=False, quote=False, name="failed_query")
    specific_issue = Column(Text, nullable=False, quote=False, name="specific_issue")
    corrected_query = Column(Text, nullable=True, quote=False, name="corrected_query")
    user_feedback = Column(Text, nullable=True, quote=False, name="user_feedback")
    user_correction = Column(Text, nullable=True, quote=False, name="user_correction")
    message_id = Column(String(255), nullable=True, quote=False, name="message_id")

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_learning_memories")


class AIPrediction(Base, BaseEntity):
    """AI Predictions table - logs ML model predictions and accuracy tracking."""
    __tablename__ = 'ai_predictions'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    model_name = Column(String(100), nullable=False, quote=False, name="model_name")
    model_version = Column(String(50), nullable=True, quote=False, name="model_version")
    input_data = Column(Text, nullable=False, quote=False, name="input_data")  # JSON as text
    prediction_result = Column(Text, nullable=False, quote=False, name="prediction_result")  # JSON as text
    confidence_score = Column(Float, nullable=True, quote=False, name="confidence_score")
    actual_outcome = Column(Text, nullable=True, quote=False, name="actual_outcome")  # JSON as text
    accuracy_score = Column(Float, nullable=True, quote=False, name="accuracy_score")
    prediction_type = Column(String(50), nullable=False, quote=False, name="prediction_type")  # 'trajectory', 'complexity', 'risk', etc.
    validated_at = Column(DateTime, nullable=True, quote=False, name="validated_at")

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_predictions")


class AIPerformanceMetric(Base, BaseEntity):
    """AI Performance Metrics table - tracks system performance metrics for ML monitoring."""
    __tablename__ = 'ai_performance_metrics'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    metric_name = Column(String(100), nullable=False, quote=False, name="metric_name")
    metric_value = Column(Float, nullable=False, quote=False, name="metric_value")
    metric_unit = Column(String(20), nullable=True, quote=False, name="metric_unit")
    measurement_timestamp = Column(DateTime, nullable=False, default=func.now(), quote=False, name="measurement_timestamp")
    context_data = Column(Text, nullable=True, quote=False, name="context_data")  # JSON as text
    service_name = Column(String(50), nullable=True, quote=False, name="service_name")  # 'backend', 'etl', 'ai'

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_performance_metrics")


class MLAnomalyAlert(Base, BaseEntity):
    """ML Anomaly Alerts table - tracks anomalies detected by ML monitoring systems."""
    __tablename__ = 'ml_anomaly_alerts'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    model_name = Column(String(100), nullable=False, quote=False, name="model_name")
    severity = Column(String(20), nullable=False, quote=False, name="severity")  # 'low', 'medium', 'high', 'critical'
    alert_data = Column(JSON, nullable=False, quote=False, name="alert_data")
    acknowledged = Column(Boolean, default=False, quote=False, name="acknowledged")
    acknowledged_by = Column(Integer, quote=False, name="acknowledged_by")
    acknowledged_at = Column(DateTime(timezone=True), quote=False, name="acknowledged_at")

    # Relationships
    tenant = relationship("Tenant", back_populates="ml_anomaly_alerts")


# ===== PHASE 3-1: NEW MODELS FOR CLEAN ARCHITECTURE =====

class QdrantVector(Base):
    """Tracks vector references in Qdrant with client isolation (Phase 3-1)."""
    __tablename__ = 'qdrant_vectors'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'table_name', 'record_id', 'vector_type'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, quote=False, name="tenant_id")
    table_name = Column(String(50), nullable=False, quote=False, name="table_name")
    record_id = Column(Integer, nullable=False, quote=False, name="record_id")
    qdrant_collection = Column(String(100), nullable=False, quote=False, name="qdrant_collection")
    qdrant_point_id = Column(UUID(as_uuid=False), nullable=False, quote=False, name="qdrant_point_id")  # UUID type
    vector_type = Column(String(50), nullable=False, quote=False, name="vector_type")  # 'content', 'summary', 'metadata'
    embedding_model = Column(String(100), nullable=False, quote=False, name="embedding_model")
    embedding_provider = Column(String(50), nullable=False, quote=False, name="embedding_provider")

    last_updated_at = Column(DateTime(timezone=True), default=func.now(), quote=False, name="last_updated_at")

    # Relationships
    tenant = relationship("Tenant", back_populates="qdrant_vectors")





class AIUsageTracking(Base):
    """AI usage trackings table (inspired by WrenAI's cost monitoring)."""
    __tablename__ = 'ai_usage_trackings'

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, quote=False, name="tenant_id")
    provider = Column(String(50), nullable=False, quote=False, name="provider")  # 'openai', 'azure', 'sentence_transformers'
    operation = Column(String(50), nullable=False, quote=False, name="operation")  # 'embedding', 'text_generation', 'analysis'
    model_name = Column(String(100), quote=False, name="model_name")
    input_count = Column(Integer, default=0, quote=False, name="input_count")
    input_tokens = Column(Integer, default=0, quote=False, name="input_tokens")
    output_tokens = Column(Integer, default=0, quote=False, name="output_tokens")
    total_tokens = Column(Integer, default=0, quote=False, name="total_tokens")
    cost = Column(Numeric(10, 4), default=0.0, quote=False, name="cost")
    request_metadata = Column(JSON, default={}, quote=False, name="request_metadata")
    created_at = Column(DateTime(timezone=True), default=func.now(), quote=False, name="created_at")

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_usage_trackings")


class VectorizationQueue(Base):
    """Async vectorization queue for ETL processing."""
    __tablename__ = 'vectorization_queue'
    __table_args__ = (
        UniqueConstraint('table_name', 'external_id', 'operation', 'tenant_id'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Core queue fields
    table_name = Column(String(50), nullable=False, quote=False, name="table_name")
    external_id = Column(String(255), nullable=False, quote=False, name="external_id")  # External system ID
    operation = Column(String(10), nullable=False, quote=False, name="operation")  # 'insert', 'update', 'delete'

    # Status tracking
    status = Column(String(20), nullable=False, default='pending', quote=False, name="status")  # 'pending', 'processing', 'completed', 'failed'

    # Timestamps
    created_at = Column(DateTime, default=func.now(), quote=False, name="created_at")
    started_at = Column(DateTime, quote=False, name="started_at")
    completed_at = Column(DateTime, quote=False, name="completed_at")

    # Error handling
    error_message = Column(Text, quote=False, name="error_message")
    last_error_at = Column(DateTime, quote=False, name="last_error_at")

    # Embedded data for processing
    entity_data = Column(JSON, quote=False, name="entity_data")  # Store extracted data directly
    qdrant_metadata = Column(JSON, quote=False, name="qdrant_metadata")  # Pre-computed Qdrant fields

    # Tenant isolation
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, quote=False, name="tenant_id")

    # Relationships
    tenant = relationship("Tenant", back_populates="vectorization_queue")



class ProjectIssueType(Base, IntegrationBaseEntity):
    """Projects issue types discovery table"""
    __tablename__ = 'projects_issue_types'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, quote=False, name="project_id")
    jira_issuetype_id = Column(String, nullable=False, quote=False, name="jira_issuetype_id")
    jira_issuetype_name = Column(String, nullable=False, quote=False, name="jira_issuetype_name")
    jira_issuetype_description = Column(Text, quote=False, name="jira_issuetype_description")
    hierarchy_level = Column(Integer, quote=False, name="hierarchy_level")
    is_subtask = Column(Boolean, default=False, quote=False, name="is_subtask")
    discovered_at = Column(DateTime, quote=False, name="discovered_at", default=func.now())
    last_seen_at = Column(DateTime, quote=False, name="last_seen_at", default=func.now())
    is_active = Column(Boolean, default=True, quote=False, name="is_active")

    # Relationships
    project = relationship("Project", back_populates="issue_types")
    tenant = relationship("Tenant", back_populates="projects_issue_types")
    integration = relationship("Integration", back_populates="projects_issue_types")


class RawExtractionData(Base, IntegrationBaseEntity):
    """Raw data storage for ETL pipeline - simplified structure"""
    __tablename__ = 'raw_extraction_data'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    type = Column(String(50), nullable=False, quote=False, name="type")  # 'jira_custom_fields', 'github_prs', etc.
    raw_data = Column(JSON, nullable=False, quote=False, name="raw_data")  # Complete API response (exact payload)
    status = Column(String(20), default='pending', quote=False, name="status")  # 'pending', 'processing', 'completed', 'failed'
    error_details = Column(JSON, nullable=True, quote=False, name="error_details")  # Error information if processing failed

    # Relationships
    tenant = relationship("Tenant", back_populates="raw_extraction_data")
    integration = relationship("Integration", back_populates="raw_extraction_data")
