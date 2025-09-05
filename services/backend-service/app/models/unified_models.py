"""
Unified data models for Backend Service - Phase 3-1 Clean Architecture.
Based on existing snowflake_db_manager.py model with additions for development data and AI capabilities.
Updated for Phase 3-1: Vector columns removed, Qdrant integration, AI provider support.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Text, PrimaryKeyConstraint, func, Boolean, Index, text, UniqueConstraint, ARRAY, JSON, Numeric
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator, Text as SQLText
from typing import Dict, Any, Optional, List
import json




Base = declarative_base()


class Client(Base):
    """Clients table to manage different client organizations."""
    __tablename__ = 'clients'
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
    integrations = relationship("Integration", back_populates="client")
    projects = relationship("Project", back_populates="client")
    issuetypes = relationship("Issuetype", back_populates="client")
    statuses = relationship("Status", back_populates="client")
    status_mappings = relationship("StatusMapping", back_populates="client")
    workflows = relationship("Workflow", back_populates="client")
    issuetype_mappings = relationship("IssuetypeMapping", back_populates="client")
    issuetype_hierarchies = relationship("IssuetypeHierarchy", back_populates="client")
    issues = relationship("Issue", back_populates="client")
    changelogs = relationship("IssueChangelog", back_populates="client")
    repositories = relationship("Repository", back_populates="client")
    pull_requests = relationship("PullRequest", back_populates="client")
    pull_request_reviews = relationship("PullRequestReview", back_populates="client")
    pull_request_commits = relationship("PullRequestCommit", back_populates="client")
    pull_request_comments = relationship("PullRequestComment", back_populates="client")
    jira_pull_request_links = relationship("JiraPullRequestLinks", back_populates="client")
    system_settings = relationship("SystemSettings", back_populates="client")
    color_settings = relationship("ClientColorSettings", back_populates="client")

    # AI Enhancement: ML monitoring relationships
    ai_learning_memories = relationship("AILearningMemory", back_populates="client")
    ai_predictions = relationship("AIPrediction", back_populates="client")
    ai_performance_metrics = relationship("AIPerformanceMetric", back_populates="client")
    ml_anomaly_alerts = relationship("MLAnomalyAlert", back_populates="client")

    # Phase 3-1: New AI architecture relationships
    qdrant_vectors = relationship("QdrantVector", back_populates="client")
    ai_preferences = relationship("ClientAIPreferences", back_populates="client")
    ai_configuration = relationship("ClientAIConfiguration", back_populates="client")
    ai_usage_tracking = relationship("AIUsageTracking", back_populates="client")


class BaseEntity:
    """Base class with audit fields for client-level entities (no integration)."""
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False, quote=False, name="client_id")
    active = Column(Boolean, nullable=False, default=True, quote=False, name="active")
    created_at = Column(DateTime, quote=False, name="created_at", default=func.now())
    last_updated_at = Column(DateTime, quote=False, name="last_updated_at", default=func.now())


class IntegrationBaseEntity:
    """Base class with audit fields for integration-specific entities."""
    integration_id = Column(Integer, ForeignKey('integrations.id'), nullable=False, quote=False, name="integration_id")
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False, quote=False, name="client_id")
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
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "client_id": self.client_id,
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
    __tablename__ = 'user_sessions'
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
    __tablename__ = 'user_permissions'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, quote=False, name="user_id")
    resource = Column(String(100), nullable=False, quote=False, name="resource")  # 'etl_jobs', 'dashboards', 'settings'
    action = Column(String(50), nullable=False, quote=False, name="action")  # 'read', 'execute', 'delete', 'admin'
    granted = Column(Boolean, nullable=False, default=True, quote=False, name="granted")  # True = grant, False = deny

    # Relationships
    user = relationship("User", back_populates="permissions")




class Integration(Base, BaseEntity):
    """Clean integrations table (Phase 3-1)"""
    __tablename__ = 'integrations'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Core integration fields
    provider = Column(String(50), nullable=False, quote=False, name="provider")  # 'jira', 'github', 'openai', 'wex_ai_gateway'
    type = Column(String(50), nullable=False, quote=False, name="type")  # 'data_source', 'ai_provider', 'notification'
    username = Column(String, quote=False, name="username")
    password = Column(String, quote=False, name="password")
    base_url = Column(Text, quote=False, name="base_url")
    base_search = Column(String, quote=False, name="base_search")
    model = Column(String(100), quote=False, name="model")  # AI model name: 'azure-gpt-4o-mini', 'bedrock-claude-sonnet-4-v1'

    # JSON configuration columns for complex settings
    model_config = Column(JSON, default={}, quote=False, name="model_config")  # AI model configuration
    performance_config = Column(JSON, default={}, quote=False, name="performance_config")  # Rate limits, timeouts, etc.
    configuration = Column(JSON, default={}, quote=False, name="configuration")  # General configuration
    provider_metadata = Column(JSON, default={}, quote=False, name="provider_metadata")  # Provider-specific metadata
    cost_config = Column(JSON, default={}, quote=False, name="cost_config")  # Cost tracking and limits
    fallback_integration_id = Column(Integer, quote=False, name="fallback_integration_id")  # FK to another integration for fallback

    # Relationships
    client = relationship("Client", back_populates="integrations")
    project_objects = relationship("Project", back_populates="integration")
    issuetypes = relationship("Issuetype", back_populates="integration")
    statuses = relationship("Status", back_populates="integration")
    issues = relationship("Issue", back_populates="integration")
    issue_changelogs = relationship("IssueChangelog", back_populates="integration")
    workflows = relationship("Workflow", back_populates="integration")
    repositories = relationship("Repository", back_populates="integration")
    pull_requests = relationship("PullRequest", back_populates="integration")
    pull_request_reviews = relationship("PullRequestReview", back_populates="integration")
    pull_request_commits = relationship("PullRequestCommit", back_populates="integration")
    pull_request_comments = relationship("PullRequestComment", back_populates="integration")
    jira_pull_request_links = relationship("JiraPullRequestLinks", back_populates="integration")
    job_schedules = relationship("JobSchedule", back_populates="integration")
    status_mappings = relationship("StatusMapping", back_populates="integration")
    issuetype_hierarchies = relationship("IssuetypeHierarchy", back_populates="integration")
    issuetype_mappings = relationship("IssuetypeMapping", back_populates="integration")

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
    client = relationship("Client", back_populates="projects")
    integration = relationship("Integration", back_populates="project_objects")
    issuetypes = relationship("Issuetype", secondary="projects_issuetypes", back_populates="projects")
    statuses = relationship("Status", secondary="projects_statuses", back_populates="projects")
    issues = relationship("Issue", back_populates="project")

class ProjectsIssuetypes(Base):
    """Relationship table between projects and issue types"""
    __tablename__ = 'projects_issuetypes'
    __table_args__ = (PrimaryKeyConstraint('project_id', 'issuetype_id'), {'quote': False})

    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True, quote=False, name="project_id")
    issuetype_id = Column(Integer, ForeignKey('issuetypes.id'), primary_key=True, quote=False, name="issuetype_id")

class ProjectsStatuses(Base):
    """Relationship table between projects and statuses"""
    __tablename__ = 'projects_statuses'
    __table_args__ = (PrimaryKeyConstraint('project_id', 'status_id'), {'quote': False})

    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True, quote=False, name="project_id")
    status_id = Column(Integer, ForeignKey('statuses.id'), primary_key=True, quote=False, name="status_id")

class Issuetype(Base, IntegrationBaseEntity):
    """Issue types table"""
    __tablename__ = 'issuetypes'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    original_name = Column(String, quote=False, nullable=False, name="original_name")
    issuetype_mapping_id = Column(Integer, ForeignKey('issuetype_mappings.id'), quote=False, nullable=True, name="issuetype_mapping_id")
    description = Column(String, quote=False, name="description")
    hierarchy_level = Column(Integer, quote=False, nullable=False, name="hierarchy_level")

    # Relationships
    client = relationship("Client", back_populates="issuetypes")
    integration = relationship("Integration", back_populates="issuetypes")
    projects = relationship("Project", secondary="projects_issuetypes", back_populates="issuetypes")
    issuetype_mapping = relationship("IssuetypeMapping", back_populates="issuetypes")
    issues = relationship("Issue", back_populates="issuetype")

class StatusMapping(Base, IntegrationBaseEntity):
    """Status Mapping table - maps raw status names to standardized flow steps"""
    __tablename__ = 'status_mappings'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    status_from = Column(String, quote=False, nullable=False, name="status_from")
    status_to = Column(String, quote=False, nullable=False, name="status_to")
    status_category = Column(String, quote=False, nullable=False, name="status_category")
    workflow_id = Column(Integer, ForeignKey('workflows.id'), quote=False, nullable=True, name="workflow_id")

    # Relationships
    client = relationship("Client", back_populates="status_mappings")
    integration = relationship("Integration", back_populates="status_mappings")
    workflow = relationship("Workflow", back_populates="status_mappings")
    statuses = relationship("Status", back_populates="status_mapping")

class IssuetypeHierarchy(Base, IntegrationBaseEntity):
    """Issue Type Hierarchies table - defines hierarchy levels and their properties"""
    __tablename__ = 'issuetype_hierarchies'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    level_name = Column(String, quote=False, nullable=False, name="level_name")
    level_number = Column(Integer, quote=False, nullable=False, name="level_number")
    description = Column(String, quote=False, nullable=True, name="description")

    # Relationships
    client = relationship("Client", back_populates="issuetype_hierarchies")
    integration = relationship("Integration", back_populates="issuetype_hierarchies")
    issuetype_mappings = relationship("IssuetypeMapping", back_populates="issuetype_hierarchy")


class IssuetypeMapping(Base, IntegrationBaseEntity):
    """Issue Type Mapping table - maps raw issue type names to standardized issue types"""
    __tablename__ = 'issuetype_mappings'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    issuetype_from = Column(String, quote=False, nullable=False, name="issuetype_from")
    issuetype_to = Column(String, quote=False, nullable=False, name="issuetype_to")
    issuetype_hierarchy_id = Column(Integer, ForeignKey('issuetype_hierarchies.id'), quote=False, nullable=False, name="issuetype_hierarchy_id")

    # Relationships
    client = relationship("Client", back_populates="issuetype_mappings")
    integration = relationship("Integration", back_populates="issuetype_mappings")
    issuetypes = relationship("Issuetype", back_populates="issuetype_mapping")
    issuetype_hierarchy = relationship("IssuetypeHierarchy", back_populates="issuetype_mappings")

class Workflow(Base, IntegrationBaseEntity):
    """Workflows table - client and integration-specific workflow steps"""
    __tablename__ = 'workflows'
    __table_args__ = (
        # Ensure only one commitment point per client/integration combination
        Index('idx_unique_commitment_point_per_client_integration', 'client_id', 'integration_id',
              postgresql_where=text('is_commitment_point = true')),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    step_name = Column(String, quote=False, nullable=False, name="step_name")  # Renamed from name
    step_number = Column(Integer, quote=False, nullable=True, name="step_number")
    step_category = Column(String, quote=False, nullable=False, name="step_category")
    is_commitment_point = Column(Boolean, quote=False, nullable=False, default=False, name="is_commitment_point")  # Commitment point for lead time calculation

    # Relationships
    client = relationship("Client", back_populates="workflows")
    integration = relationship("Integration", back_populates="workflows")
    status_mappings = relationship("StatusMapping", back_populates="workflow")

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
    client = relationship("Client", back_populates="statuses")
    integration = relationship("Integration", back_populates="statuses")
    projects = relationship("Project", secondary="projects_statuses", back_populates="statuses")
    status_mapping = relationship("StatusMapping", back_populates="statuses")
    issues = relationship("Issue", back_populates="status")

class Issue(Base, IntegrationBaseEntity):
    """Main issues table"""
    __tablename__ = 'issues'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    key = Column(String, quote=False, name="key")
    project_id = Column(Integer, ForeignKey('projects.id'), quote=False, name="project_id")
    team = Column(String, quote=False, name="team")
    summary = Column(String, quote=False, name="summary")
    issuetype_id = Column(Integer, ForeignKey('issuetypes.id'), quote=False, name="issuetype_id")
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

    # Relationships
    client = relationship("Client", back_populates="issues")
    project = relationship("Project", back_populates="issues")
    issuetype = relationship("Issuetype", back_populates="issues")
    status = relationship("Status", back_populates="issues")
    integration = relationship("Integration", back_populates="issues")



    # Note: Parent-child relationships now use external_id instead of foreign key
    # This provides better data integrity and simpler import logic

    # New relationships for development data
    pull_requests = relationship("PullRequest", back_populates="issue")
    changelogs = relationship("IssueChangelog", back_populates="issue")
    pr_links = relationship("JiraPullRequestLinks", back_populates="issue")

class IssueChangelog(Base, IntegrationBaseEntity):
    """Issue status change history table"""
    __tablename__ = 'issue_changelogs'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    issue_id = Column(Integer, ForeignKey('issues.id'), quote=False, nullable=False, name="issue_id")
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
    client = relationship("Client", back_populates="changelogs")
    integration = relationship("Integration", back_populates="issue_changelogs")
    issue = relationship("Issue", back_populates="changelogs")
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
    client = relationship("Client", back_populates="repositories")
    integration = relationship("Integration", back_populates="repositories")
    pull_requests = relationship("PullRequest", back_populates="repository")

class PullRequest(Base, IntegrationBaseEntity):
    """Pull Requests table - can be updated by both Jira and GitHub integrations"""
    __tablename__ = 'pull_requests'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")
    external_repo_id = Column(String, quote=False, name="external_repo_id")  # GitHub repository ID for linking
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False, quote=False, name="repository_id")
    issue_id = Column(Integer, ForeignKey('issues.id'), nullable=True, quote=False, name="issue_id")
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
    repository = relationship("Repository", back_populates="pull_requests")
    issue = relationship("Issue", back_populates="pull_requests")
    client = relationship("Client", back_populates="pull_requests")
    integration = relationship("Integration", back_populates="pull_requests")

    # New relationships for detailed PR conversation tracking
    reviews = relationship("PullRequestReview", back_populates="pull_request")
    commits = relationship("PullRequestCommit", back_populates="pull_request")
    comments = relationship("PullRequestComment", back_populates="pull_request")

class PullRequestReview(Base, IntegrationBaseEntity):
    """Pull Request Reviews table - stores each formal review submission"""
    __tablename__ = 'pull_request_reviews'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")  # GitHub review ID
    pull_request_id = Column(Integer, ForeignKey('pull_requests.id'), nullable=False, quote=False, name="pull_request_id")
    author_login = Column(String, quote=False, name="author_login")  # Reviewer's GitHub username
    state = Column(String, quote=False, name="state")  # APPROVED, CHANGES_REQUESTED, COMMENTED
    body = Column(Text, quote=False, name="body")  # Review comment text
    submitted_at = Column(DateTime, quote=False, name="submitted_at")  # Review submission timestamp

    # Relationships
    pull_request = relationship("PullRequest", back_populates="reviews")
    client = relationship("Client", back_populates="pull_request_reviews")
    integration = relationship("Integration", back_populates="pull_request_reviews")

class PullRequestCommit(Base, IntegrationBaseEntity):
    """Pull Request Commits table - stores each individual commit associated with a PR"""
    __tablename__ = 'pull_request_commits'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")  # SHA, the commit hash
    pull_request_id = Column(Integer, ForeignKey('pull_requests.id'), nullable=False, quote=False, name="pull_request_id")
    author_name = Column(String, quote=False, name="author_name")  # Commit author name
    author_email = Column(String, quote=False, name="author_email")  # Commit author email
    committer_name = Column(String, quote=False, name="committer_name")  # Committer name
    committer_email = Column(String, quote=False, name="committer_email")  # Committer email
    message = Column(Text, quote=False, name="message")  # Commit message
    authored_date = Column(DateTime, quote=False, name="authored_date")  # Commit timestamp
    committed_date = Column(DateTime, quote=False, name="committed_date")  # Committed timestamp

    # Relationships
    pull_request = relationship("PullRequest", back_populates="commits")
    client = relationship("Client", back_populates="pull_request_commits")
    integration = relationship("Integration", back_populates="pull_request_commits")

class PullRequestComment(Base, IntegrationBaseEntity):
    """Pull Request Comments table - stores all comments made on the PR's main thread and on specific lines of code"""
    __tablename__ = 'pull_request_comments'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    external_id = Column(String, quote=False, name="external_id")  # GitHub comment ID
    pull_request_id = Column(Integer, ForeignKey('pull_requests.id'), nullable=False, quote=False, name="pull_request_id")
    author_login = Column(String, quote=False, name="author_login")  # Comment author's GitHub username
    body = Column(Text, quote=False, name="body")  # Comment text
    comment_type = Column(String, quote=False, name="comment_type")  # 'issue' (main thread) or 'review' (line-specific)
    path = Column(String, quote=False, name="path")  # File path for line-specific comments
    position = Column(Integer, quote=False, name="position")  # Line position for line-specific comments
    line = Column(Integer, quote=False, name="line")  # Line number for line-specific comments
    created_at_github = Column(DateTime, quote=False, name="created_at_github")  # GitHub timestamp
    updated_at_github = Column(DateTime, quote=False, name="updated_at_github")  # GitHub update timestamp

    # Relationships
    pull_request = relationship("PullRequest", back_populates="comments")
    client = relationship("Client", back_populates="pull_request_comments")
    integration = relationship("Integration", back_populates="pull_request_comments")

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
    client = relationship("Client", back_populates="system_settings")

    def get_typed_value(self):
        """Returns the setting value converted to its proper type."""
        if self.setting_type == 'integer':
            return int(self.setting_value)
        elif self.setting_type == 'boolean':
            return self.setting_value.lower() in ('true', '1', 'yes', 'on')
        elif self.setting_type == 'json':
            import json
            return json.loads(self.setting_value)
        else:
            return self.setting_value

    def set_typed_value(self, value):
        """Sets the setting value from a typed value."""
        if self.setting_type == 'integer':
            self.setting_value = str(int(value))
        elif self.setting_type == 'boolean':
            self.setting_value = str(bool(value)).lower()
        elif self.setting_type == 'json':
            import json
            self.setting_value = json.dumps(value)
        else:
            self.setting_value = str(value)


class JobSchedule(Base, IntegrationBaseEntity):
    """
    Orchestration table for managing ETL job execution with state management.

    Implements Active/Passive Job Model:
    - Active Job (Orchestrator): Checks for PENDING jobs and triggers them
    - Passive Jobs (Workers): Do the actual ETL work and manage their own state
    """

    __tablename__ = 'job_schedules'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Job identification
    job_name = Column(String, nullable=False, quote=False, name="job_name")  # 'jira_sync', 'github_sync', 'fabric_sync', 'ad_sync'
    execution_order = Column(Integer, nullable=False, quote=False, name="execution_order")  # 1, 2, 3, 4...
    status = Column(String, nullable=False, default='PENDING', quote=False, name="status")  # 'PENDING', 'RUNNING', 'FINISHED', 'PAUSED', 'INACTIVE'

    # Checkpoint management for graceful failure recovery
    last_repo_sync_checkpoint = Column(DateTime, nullable=True, quote=False, name="last_repo_sync_checkpoint")

    # Repository processing queue (JSONB array of repo objects)
    repo_processing_queue = Column(Text, nullable=True, quote=False, name="repo_processing_queue")  # JSON string for compatibility

    # GraphQL cursor-based pagination checkpoints
    last_pr_cursor = Column(String, nullable=True, quote=False, name="last_pr_cursor")
    current_pr_node_id = Column(String, nullable=True, quote=False, name="current_pr_node_id")
    last_commit_cursor = Column(String, nullable=True, quote=False, name="last_commit_cursor")
    last_review_cursor = Column(String, nullable=True, quote=False, name="last_review_cursor")
    last_comment_cursor = Column(String, nullable=True, quote=False, name="last_comment_cursor")
    last_review_thread_cursor = Column(String, nullable=True, quote=False, name="last_review_thread_cursor")

    # Execution tracking (Integration Sync Pattern)
    # last_run_started_at: Set when job starts extracting data, NEVER updated during recovery
    # last_success_at: Set when job completes successfully, used as integration.last_sync_at
    # Recovery: Always continue from last_run_started_at using cursors for pagination
    last_run_started_at = Column(DateTime, nullable=True, quote=False, name="last_run_started_at")
    last_success_at = Column(DateTime, nullable=True, quote=False, name="last_success_at")
    error_message = Column(Text, nullable=True, quote=False, name="error_message")
    retry_count = Column(Integer, default=0, quote=False, name="retry_count")

    # Relationships
    integration = relationship("Integration", back_populates="job_schedules")

    def clear_checkpoints(self):
        """Clear checkpoint data after successful completion."""
        self.last_repo_sync_checkpoint = None
        self.repo_processing_queue = None
        self.last_pr_cursor = None
        self.current_pr_node_id = None
        self.last_commit_cursor = None
        self.last_review_cursor = None
        self.last_comment_cursor = None
        self.last_review_thread_cursor = None

    def has_recovery_checkpoints(self) -> bool:
        """Check if there are any remaining recovery checkpoints."""
        return any([
            self.last_repo_sync_checkpoint is not None,
            self.repo_processing_queue is not None,
            self.last_pr_cursor is not None,
            self.current_pr_node_id is not None,
            self.last_commit_cursor is not None,
            self.last_review_cursor is not None,
            self.last_comment_cursor is not None,
            self.last_review_thread_cursor is not None
        ])

    def set_running(self):
        """Mark job as running."""
        from app.core.utils import DateTimeHelper
        self.status = 'RUNNING'
        self.last_run_started_at = DateTimeHelper.now_default()

    def set_finished(self):
        """Mark job as finished and clear checkpoints."""
        from app.core.utils import DateTimeHelper
        self.status = 'FINISHED'
        self.last_success_at = DateTimeHelper.now_default()
        self.clear_checkpoints()

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

    def set_pending_with_checkpoint(self, error_message: str, repo_checkpoint: DateTime = None,
                                   repo_queue: list = None, last_pr_cursor: str = None,
                                   current_pr_node_id: str = None, last_commit_cursor: str = None,
                                   last_review_cursor: str = None, last_comment_cursor: str = None,
                                   last_review_thread_cursor: str = None):
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
        if self.repo_processing_queue:
            import json
            repo_queue = json.loads(self.repo_processing_queue)

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
        if not self.repo_processing_queue:
            return

        import json
        queue = json.loads(self.repo_processing_queue)
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
        if not self.repo_processing_queue:
            return 0

        import json
        queue = json.loads(self.repo_processing_queue)
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
        if not self.repo_processing_queue:
            return []

        import json
        return json.loads(self.repo_processing_queue)

    def get_unfinished_repos(self):
        """Get only unfinished repositories for recovery processing."""
        if not self.repo_processing_queue:
            return []

        import json
        queue = json.loads(self.repo_processing_queue)
        return [repo for repo in queue if not repo.get("finished", False)]


class JiraPullRequestLinks(Base, IntegrationBaseEntity):
    """
    Permanent table storing Jira issue to PR links from dev_status API.

    This table stores the facts about which PRs are linked to which Jira issues,
    allowing for clean join-based queries without complex staging logic.
    """

    __tablename__ = 'jira_pull_request_links'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")

    # Foreign keys
    issue_id = Column(Integer, ForeignKey('issues.id'), nullable=False, quote=False, name="issue_id")

    # PR identification (for joining with pull_requests table)
    external_repo_id = Column(String, nullable=False, quote=False, name="external_repo_id")  # GitHub repo ID
    repo_full_name = Column(String, nullable=False, quote=False, name="repo_full_name")  # GitHub repo full name (e.g., "wexinc/health-api")
    pull_request_number = Column(Integer, nullable=False, quote=False, name="pull_request_number")

    # Metadata from dev_status API
    branch_name = Column(String, quote=False, name="branch_name")
    commit_sha = Column(String, quote=False, name="commit_sha")
    pr_status = Column(String, quote=False, name="pr_status")  # 'OPEN', 'MERGED', 'DECLINED'

    # Relationships
    issue = relationship("Issue", back_populates="pr_links")
    client = relationship("Client", back_populates="jira_pull_request_links")
    integration = relationship("Integration", back_populates="jira_pull_request_links")

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

class ClientColorSettings(Base, BaseEntity):
    """Unified color settings table with all color variants and accessibility levels."""
    __tablename__ = 'client_color_settings'
    __table_args__ = (
        UniqueConstraint('client_id', 'color_schema_mode', 'accessibility_level', 'theme_mode'),
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
    client = relationship("Client", back_populates="color_settings")


# ===================================
# AI ENHANCEMENT: ML MONITORING MODELS
# ===================================

class AILearningMemory(Base, BaseEntity):
    """AI Learning Memory table - stores user feedback and corrections for ML improvement."""
    __tablename__ = 'ai_learning_memory'
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
    client = relationship("Client", back_populates="ai_learning_memories")


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
    client = relationship("Client", back_populates="ai_predictions")


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
    client = relationship("Client", back_populates="ai_performance_metrics")


class MLAnomalyAlert(Base, BaseEntity):
    """ML Anomaly Alert table - tracks anomalies detected by ML monitoring systems."""
    __tablename__ = 'ml_anomaly_alert'
    __table_args__ = {'quote': False}

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    model_name = Column(String(100), nullable=False, quote=False, name="model_name")
    severity = Column(String(20), nullable=False, quote=False, name="severity")  # 'low', 'medium', 'high', 'critical'
    alert_data = Column(JSON, nullable=False, quote=False, name="alert_data")
    acknowledged = Column(Boolean, default=False, quote=False, name="acknowledged")
    acknowledged_by = Column(Integer, quote=False, name="acknowledged_by")
    acknowledged_at = Column(DateTime(timezone=True), quote=False, name="acknowledged_at")

    # Relationships
    client = relationship("Client", back_populates="ml_anomaly_alerts")


# ===== PHASE 3-1: NEW MODELS FOR CLEAN ARCHITECTURE =====

class QdrantVector(Base, BaseEntity):
    """Tracks vector references in Qdrant with client isolation (Phase 3-1)."""
    __tablename__ = 'qdrant_vectors'
    __table_args__ = (
        UniqueConstraint('client_id', 'table_name', 'record_id', 'vector_type'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    table_name = Column(String(50), nullable=False, quote=False, name="table_name")
    record_id = Column(Integer, nullable=False, quote=False, name="record_id")
    qdrant_collection = Column(String(100), nullable=False, quote=False, name="qdrant_collection")
    qdrant_point_id = Column(String(36), nullable=False, quote=False, name="qdrant_point_id")  # UUID as string
    vector_type = Column(String(50), nullable=False, quote=False, name="vector_type")  # 'content', 'summary', 'metadata'
    embedding_model = Column(String(100), nullable=False, quote=False, name="embedding_model")
    embedding_provider = Column(String(50), nullable=False, quote=False, name="embedding_provider")
    last_updated_at = Column(DateTime(timezone=True), default=func.now(), quote=False, name="last_updated_at")

    # Relationships
    client = relationship("Client", back_populates="qdrant_vectors")


class ClientAIPreferences(Base, BaseEntity):
    """Client AI preferences table (inspired by WrenAI's configuration system)."""
    __tablename__ = 'client_ai_preferences'
    __table_args__ = (
        UniqueConstraint('client_id', 'preference_type'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    preference_type = Column(String(50), nullable=False, quote=False, name="preference_type")  # 'default_models', 'performance', 'cost_limits'
    configuration = Column(JSON, default={}, quote=False, name="configuration")

    # Relationships
    client = relationship("Client", back_populates="ai_preferences")


class ClientAIConfiguration(Base, BaseEntity):
    """Client AI configuration table (inspired by WrenAI's pipeline configuration)."""
    __tablename__ = 'client_ai_configuration'
    __table_args__ = (
        UniqueConstraint('client_id', 'config_category'),
        {'quote': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    config_category = Column(String(50), nullable=False, quote=False, name="config_category")  # 'embedding_models', 'llm_models', 'pipeline_config'
    configuration = Column(JSON, default={}, quote=False, name="configuration")

    # Relationships
    client = relationship("Client", back_populates="ai_configuration")


class AIUsageTracking(Base, BaseEntity):
    """AI usage tracking table (inspired by WrenAI's cost monitoring)."""
    __tablename__ = 'ai_usage_tracking'

    id = Column(Integer, primary_key=True, autoincrement=True, quote=False, name="id")
    provider = Column(String(50), nullable=False, quote=False, name="provider")  # 'openai', 'azure', 'sentence_transformers'
    operation = Column(String(50), nullable=False, quote=False, name="operation")  # 'embedding', 'text_generation', 'analysis'
    model_name = Column(String(100), quote=False, name="model_name")
    input_count = Column(Integer, default=0, quote=False, name="input_count")
    input_tokens = Column(Integer, default=0, quote=False, name="input_tokens")
    output_tokens = Column(Integer, default=0, quote=False, name="output_tokens")
    total_tokens = Column(Integer, default=0, quote=False, name="total_tokens")
    cost = Column(Numeric(10, 4), default=0.0, quote=False, name="cost")
    request_metadata = Column(JSON, default={}, quote=False, name="request_metadata")

    # Relationships
    client = relationship("Client", back_populates="ai_usage_tracking")
