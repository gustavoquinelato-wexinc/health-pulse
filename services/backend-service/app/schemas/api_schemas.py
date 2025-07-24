"""
Pydantic schemas for Backend Service API requests and responses.
Defines data models for authentication, user management, and admin APIs.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class HealthResponse(BaseModel):
    """Response for health check."""
    status: str = "healthy"
    message: str = "Backend Service is running"
    database_status: str
    database_message: str
    version: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Authentication and User Management Schemas

class LoginRequest(BaseModel):
    """Request for user login."""
    email: str = Field(description="User email address")
    password: str = Field(description="User password")

class LoginResponse(BaseModel):
    """Response for successful login."""
    success: bool = Field(default=True, description="Login success status")
    token: str = Field(description="JWT authentication token")
    user: Dict = Field(description="User information")

class TokenValidationResponse(BaseModel):
    """Response for token validation."""
    valid: bool = Field(description="Whether the token is valid")
    user: Optional[Dict] = Field(description="User information if token is valid")

# Admin API Schemas

class UserCreateRequest(BaseModel):
    """Request to create a new user."""
    email: str = Field(description="User email address")
    password: str = Field(description="User password")
    first_name: Optional[str] = Field(description="User first name")
    last_name: Optional[str] = Field(description="User last name")
    role: str = Field(description="User role")
    is_admin: bool = Field(default=False, description="Whether user is admin")

class UserUpdateRequest(BaseModel):
    """Request to update user information."""
    first_name: Optional[str] = Field(description="User first name")
    last_name: Optional[str] = Field(description="User last name")
    role: Optional[str] = Field(description="User role")
    is_admin: Optional[bool] = Field(description="Whether user is admin")
    active: Optional[bool] = Field(description="Whether user is active")

# Session Management Schemas

class SessionResponse(BaseModel):
    """Response for session information."""
    session_id: int
    user_id: int
    email: str
    login_time: Optional[str] = None
    last_activity: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    active: bool

# Error Response Schema

class ErrorResponse(BaseModel):
    """Standard response for errors."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
