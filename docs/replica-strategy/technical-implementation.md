# Technical Implementation Guide
## Database Router & Connection Management

### 🏗️ **Database Router Architecture**

#### **Core Components**

```python
# services/backend-service/app/core/database_router.py
class DatabaseRouter:
    """
    Intelligent database routing for read/write operations.
    Routes queries to appropriate database instance based on operation type.
    """
    
    def __init__(self):
        self.primary_engine = None      # Write operations
        self.replica_engine = None      # Read operations
        self.replica_available = True   # Health status
        
    def get_write_session(self) -> Session:
        """Always routes to primary database"""
        return self._get_primary_session()
    
    def get_read_session(self) -> Session:
        """Routes to replica if available, fallback to primary"""
        if self.replica_available:
            return self._get_replica_session()
        return self._get_primary_session()
    
    def route_query(self, operation_type: str, table: str = None) -> Session:
        """Smart routing based on operation and table"""
        # Implementation details below...
```

#### **Operation-Based Routing Rules**

```python
# CORRECTED APPROACH: Route by operation context, not table names
# Entire database is replicated - routing is based on operation purpose

ROUTING_RULES = {
    # Always Primary (immediate consistency required)
    'primary_operations': [
        # All Write Operations (regardless of table)
        'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'UPSERT',

        # Real-time Read Operations
        'user_login',           # Authentication checks
        'session_validation',   # User session verification
        'job_control',          # Start/stop/pause ETL jobs
        'admin_config',         # ETL admin page operations
        'client_mgmt',          # Client settings, logo uploads
        'integration_setup'     # API credentials, connection tests
    ],

    # Can use Replica (eventual consistency acceptable)
    'replica_operations': [
        # Analytics & Reporting Operations
        'dashboard_query',      # Dashboard metrics (can JOIN all tables)
        'analytics_report',     # Historical analysis across tables
        'dora_metrics',         # DORA calculations (multi-table JOINs)
        'trend_analysis',       # Issue/PR trend reports
        'data_export',          # Export operations for reporting
        'visualization_data'    # Chart/graph data generation
    ]
}

# Example Analytics Query (uses replica, JOINs multiple tables)
def get_dora_metrics():
    with get_read_session() as session:  # → REPLICA
        # This query JOINs across multiple tables - ALL are available in replica
        return session.execute("""
            SELECT
                i.summary,
                s.name as status_name,        -- status table
                it.name as issuetype_name,    -- issuetype table
                p.name as project_name,       -- project table
                c.name as client_name,        -- client table
                w.step_name                   -- workflow table
            FROM issues i
            JOIN statuses s ON i.status_id = s.id
            JOIN issuetypes it ON i.issuetype_id = it.id
            JOIN projects p ON i.project_id = p.id
            JOIN clients c ON i.client_id = c.id
            JOIN workflows w ON s.workflow_id = w.id
            WHERE i.created_at > :start_date
        """)
```

### 🔧 **Connection Pool Configuration**

#### **Optimized Pool Settings**

```python
# services/backend-service/app/core/config.py
class Settings(BaseSettings):
    # Primary Database Configuration
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str

    # Read Replica Configuration
    POSTGRES_REPLICA_HOST: Optional[str] = Field(default=None, env="POSTGRES_REPLICA_HOST")
    POSTGRES_REPLICA_PORT: int = Field(default=5432, env="POSTGRES_REPLICA_PORT")

    # Primary Database Pool Settings (Write-heavy operations)
    DB_POOL_SIZE: int = Field(default=5, env="DB_POOL_SIZE")                    # Default 5, optimized 20
    DB_MAX_OVERFLOW: int = Field(default=10, env="DB_MAX_OVERFLOW")             # Default 10, optimized 30
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")             # Default 30, optimized 60
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")           # 1 hour

    # Replica Database Pool Settings (Read-heavy operations)
    DB_REPLICA_POOL_SIZE: int = Field(default=5, env="DB_REPLICA_POOL_SIZE")    # Optimized 15
    DB_REPLICA_MAX_OVERFLOW: int = Field(default=10, env="DB_REPLICA_MAX_OVERFLOW") # Optimized 20
    DB_REPLICA_POOL_TIMEOUT: int = Field(default=30, env="DB_REPLICA_POOL_TIMEOUT") # Optimized 30

    # Feature Flags
    USE_READ_REPLICA: bool = Field(default=False, env="USE_READ_REPLICA")
    REPLICA_FALLBACK_ENABLED: bool = Field(default=True, env="REPLICA_FALLBACK_ENABLED")

    @property
    def postgres_replica_connection_string(self) -> str:
        """Read replica connection string (falls back to primary if no replica configured)"""
        replica_host = self.POSTGRES_REPLICA_HOST or self.POSTGRES_HOST
        replica_port = self.POSTGRES_REPLICA_PORT if self.POSTGRES_REPLICA_HOST else self.POSTGRES_PORT
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{replica_host}:{replica_port}/{self.POSTGRES_DATABASE}"
```

#### **Specialized Session Types**

```python
# services/etl-service/app/core/database.py
class PostgreSQLDatabase:
    
    @contextmanager
    def get_etl_session_context(self) -> Generator[Session, None, None]:
        """Long-running ETL operations with chunked commits"""
        session = self.get_write_session()
        try:
            # Optimize for bulk operations
            session.execute(text("SET statement_timeout = '300s'"))  # 5 minutes
            session.execute(text("SET idle_in_transaction_session_timeout = '600s'"))
            session.execute(text("SET synchronous_commit = off"))  # Async commits
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    @contextmanager  
    def get_analytics_session_context(self) -> Generator[Session, None, None]:
        """Read-only analytics queries"""
        session = self.get_read_session()
        try:
            # Optimize for read queries
            session.execute(text("SET statement_timeout = '60s'"))
            session.execute(text("SET transaction_read_only = on"))
            yield session
        except Exception as e:
            logger.error(f"Analytics session error: {e}")
            raise
        finally:
            session.close()
```

### 📊 **Transaction Chunking Strategy**

#### **Bulk Operation Optimization**

```python
# services/etl-service/app/jobs/github/github_bulk_processor.py
class ChunkedBulkProcessor:
    """
    Process large datasets in smaller, manageable chunks
    to prevent long-running transactions and improve concurrency.
    """
    
    def __init__(self, chunk_size: int = 100, commit_frequency: int = 5):
        self.chunk_size = chunk_size
        self.commit_frequency = commit_frequency  # Commit every N chunks
    
    async def process_bulk_data(self, data_list: List[Dict], processor_func):
        """Process data in chunks with periodic commits"""
        database = get_database()
        chunks_processed = 0
        
        for i in range(0, len(data_list), self.chunk_size):
            chunk = data_list[i:i + self.chunk_size]
            
            # Use short-lived session for each chunk
            with database.get_etl_session_context() as session:
                await processor_func(session, chunk)
                
                chunks_processed += 1
                
                # Commit every N chunks
                if chunks_processed % self.commit_frequency == 0:
                    session.commit()
                    logger.info(f"Committed chunk {chunks_processed}")
                    
                    # Yield control to prevent UI blocking
                    await asyncio.sleep(0.01)
```

#### **GitHub Job Optimization**

```python
# services/etl-service/app/jobs/github/github_job.py
async def process_repository_prs_optimized(session, repository, ...):
    """Optimized PR processing with chunking and yielding"""
    
    chunked_processor = ChunkedBulkProcessor(chunk_size=50, commit_frequency=3)
    
    # Process PRs in chunks
    all_prs = await fetch_all_prs(repository)
    
    async def process_pr_chunk(session, pr_chunk):
        for pr in pr_chunk:
            # Process individual PR
            process_single_pr(session, pr)
            
            # Yield control every 5 PRs
            if len(pr_chunk) % 5 == 0:
                await asyncio.sleep(0.003)  # 3ms yield
    
    await chunked_processor.process_bulk_data(all_prs, process_pr_chunk)
```

### 🔍 **Health Monitoring & Failover**

#### **Replica Health Monitoring**

```python
# services/backend-service/app/core/replica_monitor.py
class ReplicaHealthMonitor:
    """Monitor replica health and manage failover"""
    
    def __init__(self):
        self.replica_healthy = True
        self.last_health_check = None
        self.max_lag_seconds = 30
    
    async def check_replica_health(self) -> bool:
        """Check replica lag and availability"""
        try:
            database = get_database()
            
            # Check primary LSN
            with database.get_write_session() as primary:
                primary_lsn = primary.execute(
                    text("SELECT pg_current_wal_lsn()")
                ).scalar()
            
            # Check replica LSN
            with database.get_read_session() as replica:
                replica_lsn = replica.execute(
                    text("SELECT pg_last_wal_replay_lsn()")
                ).scalar()
            
            # Calculate lag
            lag_bytes = self._calculate_lag(primary_lsn, replica_lsn)
            lag_seconds = self._bytes_to_seconds(lag_bytes)
            
            self.replica_healthy = lag_seconds < self.max_lag_seconds
            self.last_health_check = datetime.utcnow()
            
            if not self.replica_healthy:
                logger.warning(f"Replica lag detected: {lag_seconds}s")
            
            return self.replica_healthy
            
        except Exception as e:
            logger.error(f"Replica health check failed: {e}")
            self.replica_healthy = False
            return False
    
    def should_use_replica(self) -> bool:
        """Determine if replica should be used for reads"""
        if not self.replica_healthy:
            return False
            
        # Check if health check is stale
        if self.last_health_check:
            age = datetime.utcnow() - self.last_health_check
            if age.total_seconds() > 60:  # 1 minute stale
                return False
        
        return True
```

### 🚀 **Async Processing Enhancements**

#### **Improved Yielding Strategy**

```python
# services/etl-service/app/core/async_helpers.py
class AsyncYieldManager:
    """Manage async yielding to prevent UI blocking"""
    
    def __init__(self, yield_frequency: int = 10, yield_duration: float = 0.01):
        self.yield_frequency = yield_frequency
        self.yield_duration = yield_duration
        self.operation_count = 0
    
    async def yield_if_needed(self):
        """Yield control if frequency threshold reached"""
        self.operation_count += 1
        
        if self.operation_count % self.yield_frequency == 0:
            await asyncio.sleep(self.yield_duration)
    
    async def yield_with_progress(self, current: int, total: int, 
                                 websocket_manager=None, job_name: str = None):
        """Yield with progress update"""
        await self.yield_if_needed()
        
        if websocket_manager and job_name:
            progress = (current / total) * 100
            await websocket_manager.send_progress_update(
                job_name, progress, f"Processing {current}/{total}"
            )
```

### 📈 **Performance Monitoring**

#### **Connection Pool Metrics**

```python
# services/backend-service/app/core/metrics.py
class DatabaseMetrics:
    """Collect and report database performance metrics"""
    
    @staticmethod
    def get_connection_pool_stats():
        """Get current connection pool statistics"""
        database = get_database()
        
        primary_stats = {
            'size': database.primary_engine.pool.size(),
            'checked_in': database.primary_engine.pool.checkedin(),
            'checked_out': database.primary_engine.pool.checkedout(),
            'overflow': database.primary_engine.pool.overflow(),
            'utilization': database.primary_engine.pool.checkedout() / 
                          (database.primary_engine.pool.size() + database.primary_engine.pool.overflow())
        }
        
        replica_stats = {
            'size': database.replica_engine.pool.size(),
            'checked_in': database.replica_engine.pool.checkedin(),
            'checked_out': database.replica_engine.pool.checkedout(),
            'overflow': database.replica_engine.pool.overflow(),
            'utilization': database.replica_engine.pool.checkedout() / 
                          (database.replica_engine.pool.size() + database.replica_engine.pool.overflow())
        }
        
        return {
            'primary': primary_stats,
            'replica': replica_stats,
            'timestamp': datetime.utcnow()
        }
```

### 🎯 **Real-World Platform Examples**

#### **ETL Admin Operations (Always Primary):**
```python
# services/etl-service/app/api/admin_routes.py

@router.post("/workflows")
async def create_workflow():
    # Workflow configuration changes need immediate consistency
    with get_write_session() as session:  # → PRIMARY
        # ETL jobs depend on this configuration immediately

@router.put("/status-mappings/{mapping_id}")
async def update_status_mapping():
    # Status mappings affect data processing immediately
    with get_write_session() as session:  # → PRIMARY

@router.post("/clients/{client_id}/logo")
async def upload_client_logo():
    # Client branding changes need immediate visibility
    with get_write_session() as session:  # → PRIMARY
```

#### **Dashboard Analytics (Can Use Replica):**
```python
# services/backend-service/app/api/data.py

@router.get("/dashboard/github-metrics")
async def get_github_metrics():
    # GitHub analytics can tolerate 1-2 second delay
    with get_read_session() as session:  # → REPLICA
        # Can JOIN across all tables - entire DB is replicated
        result = session.execute("""
            SELECT
                COUNT(pr.id) as pr_count,
                r.name as repo_name,
                c.name as client_name
            FROM pull_requests pr
            JOIN repositories r ON pr.repository_id = r.id
            JOIN clients c ON pr.client_id = c.id
            GROUP BY r.name, c.name
        """)

@router.get("/dashboard/dora-metrics")
async def get_dora_metrics():
    # DORA calculations need multi-table JOINs
    with get_read_session() as session:  # → REPLICA
        # Complex analytics query across multiple tables
        dora_data = session.execute("""
            SELECT
                i.key,
                i.summary,
                s.name as status,
                it.name as issue_type,
                p.name as project,
                w.step_name as workflow_step,
                ic.from_status,
                ic.to_status,
                ic.changed_at
            FROM issues i
            JOIN statuses s ON i.status_id = s.id
            JOIN issuetypes it ON i.issuetype_id = it.id
            JOIN projects p ON i.project_id = p.id
            JOIN workflows w ON s.workflow_id = w.id
            JOIN issue_changelogs ic ON i.id = ic.issue_id
            WHERE i.created_at > :start_date
        """)
```

#### **Mixed Operations (Smart Routing):**
```python
# services/backend-service/app/api/admin_routes.py

@router.get("/users")  # Reading user list
async def list_users():
    # User data needs consistency (login status, permissions)
    with get_read_session() as session:  # → PRIMARY (users in PRIMARY_TABLES)

@router.post("/users")  # Creating user
async def create_user():
    # User creation is write operation
    with get_write_session() as session:  # → PRIMARY (always)

@router.get("/pull-requests")  # Reading analytics data
async def get_pull_requests():
    # PR data for dashboards/reports
    with get_read_session() as session:  # → REPLICA (pull_requests in REPLICA_TABLES)
```

---

This technical implementation guide provides the detailed code structure and patterns needed to implement the replica strategy effectively while maintaining performance and reliability.
