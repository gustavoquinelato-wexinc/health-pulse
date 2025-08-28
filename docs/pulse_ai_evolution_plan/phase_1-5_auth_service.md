# Phase 1-5: Auth Service Compatibility

**Implemented**: NO ❌
**Duration**: Days 9-10
**Priority**: HIGH
**Dependencies**: Phase 1-1 (Database Schema) must be completed
**Can Run Parallel With**: Phase 1-3, Phase 1-4, Phase 1-6

## 🎯 Objectives

1. **User Model Updates**: Add vector column to User model
2. **Session Model Updates**: Add vector column to UserSession model  
3. **Authentication Flow Preservation**: Ensure all auth flows work with new schema
4. **Serialization Enhancement**: Handle new fields in response methods
5. **Compatibility Testing**: Verify login/logout functionality unchanged

## 📋 Implementation Tasks

### Task 1-5.1: User Model Enhancement
**File**: `services/auth-service/app/models/user.py`

**Objective**: Add vector column while preserving all functionality

### Task 1-5.2: Session Model Enhancement
**File**: `services/auth-service/app/models/session.py`

**Objective**: Add vector column to session tracking

### Task 1-5.3: Authentication Service Updates
**File**: `services/auth-service/app/core/auth.py`

**Objective**: Handle new fields in auth operations

### Task 1-5.4: API Endpoint Updates
**Files**: `services/auth-service/app/api/*.py`

**Objective**: Ensure all auth endpoints work with enhanced schema

## 🔧 Implementation Details

### Enhanced User Model
```python
# services/auth-service/app/models/user.py

from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = 'users'
    
    # All existing fields (unchanged)
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    password_hash = Column(String(255))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    # User preferences (existing)
    light_mode = Column(Boolean, default=True)
    accessibility_high_contrast = Column(Boolean, default=False)
    accessibility_large_text = Column(Boolean, default=False)
    accessibility_reduced_motion = Column(Boolean, default=False)
    
    # NEW: Vector column (matches database schema)
    embedding: Optional[List[float]] = Column(ARRAY(Float), nullable=True)
    
    # Relationships (existing)
    client = relationship("Client", back_populates="users")
    sessions = relationship("UserSession", back_populates="user")
    
    def to_dict(self, include_ml_fields: bool = False, include_sensitive: bool = False):
        """Enhanced serialization with optional ML fields"""
        result = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'client_id': self.client_id,
            'light_mode': self.light_mode,
            'accessibility_high_contrast': self.accessibility_high_contrast,
            'accessibility_large_text': self.accessibility_large_text,
            'accessibility_reduced_motion': self.accessibility_reduced_motion
        }
        
        # Include sensitive fields only if requested (for admin operations)
        if include_sensitive:
            result['password_hash'] = self.password_hash
        
        # Include ML fields only if requested
        if include_ml_fields and hasattr(self, 'embedding'):
            result['embedding'] = self.embedding
        
        return result
    
    def to_auth_response(self):
        """Standard auth response (no ML fields, no sensitive data)"""
        return self.to_dict(include_ml_fields=False, include_sensitive=False)
    
    def check_password(self, password: str) -> bool:
        """Existing password verification (unchanged)"""
        # Existing implementation preserved
        pass
    
    def set_password(self, password: str):
        """Existing password setting (unchanged)"""
        # Existing implementation preserved
        pass
```

### Enhanced Session Model
```python
# services/auth-service/app/models/session.py

class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    # All existing fields (unchanged)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True)
    
    # Session metadata (existing)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    last_activity = Column(DateTime(timezone=True))
    
    # NEW: Vector column (matches database schema)
    embedding: Optional[List[float]] = Column(ARRAY(Float), nullable=True)
    
    # Relationships (existing)
    user = relationship("User", back_populates="sessions")
    
    def to_dict(self, include_ml_fields: bool = False):
        """Enhanced serialization with optional ML fields"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'session_token': self.session_token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'active': self.active,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }
        
        # Include ML fields only if requested
        if include_ml_fields and hasattr(self, 'embedding'):
            result['embedding'] = self.embedding
        
        return result
    
    def is_expired(self) -> bool:
        """Check if session is expired (existing logic)"""
        return datetime.utcnow() > self.expires_at
    
    def extend_session(self, hours: int = 24):
        """Extend session expiration (existing logic)"""
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
        self.updated_at = datetime.utcnow()
```

### Enhanced Authentication Service
```python
# services/auth-service/app/core/auth.py

class AuthenticationService:
    """Enhanced authentication service with ML compatibility"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def create_user(self, user_data: UserCreateRequest) -> User:
        """Create user with ML compatibility"""
        try:
            user = User(
                email=user_data.email,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                is_admin=user_data.is_admin,
                is_active=True,
                client_id=user_data.client_id,
                light_mode=user_data.light_mode,
                accessibility_high_contrast=user_data.accessibility_high_contrast,
                accessibility_large_text=user_data.accessibility_large_text,
                accessibility_reduced_motion=user_data.accessibility_reduced_motion,
                
                # NEW: ML compatibility (Phase 1: Always None)
                embedding=None
            )
            
            # Set password using existing method
            user.set_password(user_data.password)
            
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            
            return user
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            self.db.rollback()
            raise
    
    async def create_user_session(self, user_id: int, session_data: dict) -> UserSession:
        """Create user session with ML compatibility"""
        try:
            session = UserSession(
                user_id=user_id,
                session_token=session_data['session_token'],
                expires_at=session_data['expires_at'],
                ip_address=session_data.get('ip_address'),
                user_agent=session_data.get('user_agent'),
                last_activity=datetime.utcnow(),
                active=True,
                
                # NEW: ML compatibility (Phase 1: Always None)
                embedding=None
            )
            
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            return session
            
        except Exception as e:
            logger.error(f"Error creating user session: {e}")
            self.db.rollback()
            raise
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user (existing logic preserved)"""
        try:
            user = self.db.query(User).filter(
                User.email == email.lower(),
                User.is_active == True
            ).first()
            
            if user and user.check_password(password):
                # Update last login
                user.last_login = datetime.utcnow()
                self.db.commit()
                return user
            
            return None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    async def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate session (existing logic preserved)"""
        try:
            session = self.db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.active == True
            ).first()
            
            if session and not session.is_expired():
                # Update last activity
                session.last_activity = datetime.utcnow()
                self.db.commit()
                return session
            
            return None
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return None
```

### Enhanced Auth API Endpoints
```python
# services/auth-service/app/api/auth.py

@router.post("/auth/login")
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """User login with enhanced schema compatibility"""
    try:
        auth_service = AuthenticationService(db)
        
        # Authenticate user (existing logic)
        user = await auth_service.authenticate_user(
            login_data.email, 
            login_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=401, 
                detail="Invalid email or password"
            )
        
        # Create session (with ML compatibility)
        session_data = {
            'session_token': generate_session_token(),
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'ip_address': request.client.host,
            'user_agent': request.headers.get('user-agent', '')
        }
        
        session = await auth_service.create_user_session(
            user.id, 
            session_data
        )
        
        # Return standard auth response (no ML fields)
        return {
            'user': user.to_auth_response(),
            'session_token': session.session_token,
            'expires_at': session.expires_at.isoformat(),
            'message': 'Login successful'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/auth/register")
async def register(
    user_data: UserRegistrationRequest,
    db: Session = Depends(get_db_session)
):
    """User registration with enhanced schema compatibility"""
    try:
        auth_service = AuthenticationService(db)
        
        # Check if user already exists
        existing_user = db.query(User).filter(
            User.email == user_data.email.lower()
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="User with this email already exists"
            )
        
        # Create user (with ML compatibility)
        user = await auth_service.create_user(user_data)
        
        # Return standard response (no ML fields)
        return {
            'user': user.to_auth_response(),
            'message': 'User registered successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.get("/auth/me")
async def get_current_user(
    include_ml_fields: bool = Query(False),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get current user info with optional ML fields"""
    try:
        return current_user.to_dict(include_ml_fields=include_ml_fields)
        
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user info")

@router.post("/auth/logout")
async def logout(
    session_token: str = Depends(get_session_token),
    db: Session = Depends(get_db_session)
):
    """User logout (existing logic preserved)"""
    try:
        # Deactivate session
        session = db.query(UserSession).filter(
            UserSession.session_token == session_token,
            UserSession.active == True
        ).first()
        
        if session:
            session.active = False
            session.updated_at = datetime.utcnow()
            db.commit()
        
        return {'message': 'Logout successful'}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")
```

## ✅ Success Criteria

1. **User Model**: Enhanced with vector column, all functionality preserved
2. **Session Model**: Enhanced with vector column, session management unchanged
3. **Authentication Flows**: Login/logout work with new schema
4. **API Endpoints**: All auth endpoints handle new fields gracefully
5. **Serialization**: Optional ML fields in responses
6. **Compatibility**: No breaking changes to existing auth functionality
7. **Testing**: All auth operations work without errors

## 📝 Testing Checklist

- [ ] User model updated with vector column
- [ ] Session model updated with vector column
- [ ] User registration works with new schema
- [ ] User login works with new schema
- [ ] Session validation works correctly
- [ ] User logout works correctly
- [ ] Password operations unchanged
- [ ] User preferences preserved
- [ ] API responses handle optional ML fields
- [ ] No auth functionality broken

## 🔄 Completion Enables

- **Phase 1-6**: Frontend can use enhanced auth responses
- **Phase 1-7**: Integration testing can validate auth functionality
- **Phase 2+**: Auth service ready for ML enhancements

## 📋 Handoff to Phase 1-6 & 1-7

**Deliverables**:
- ✅ Enhanced User model with vector column
- ✅ Enhanced UserSession model with vector column
- ✅ Updated authentication service
- ✅ Compatible auth API endpoints

**Next Phase Requirements**:
- Frontend can consume enhanced auth responses (Phase 1-6)
- Integration testing can validate auth flows (Phase 1-7)
- All services can authenticate users with new schema
