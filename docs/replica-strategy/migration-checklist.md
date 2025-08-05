# Migration Execution Checklist
## Step-by-Step Implementation Guide

### 🚀 **Pre-Migration Preparation**

#### **Environment Backup**
- [ ] **Document current configuration**
  - [ ] Current connection strings
  - [ ] Service startup commands
  - [ ] Environment variables
- [ ] **Test current functionality**
  - [ ] Run full ETL cycle (GitHub + Jira)
  - [ ] Test all dashboard features
  - [ ] Verify user authentication flows

#### **Development Environment Setup**
- [ ] **Stop current services**
  ```bash
  # Stop any running services
  docker stop pulse-postgres
  ```

---

### 📋 **PHASE 1: Database Infrastructure (Days 1-2)**

#### **Task 1.1: Create Database Compose File**
- [ ] **Create `docker-compose.db.yml`**
  ```yaml
  version: '3.8'
  services:
    postgres-primary:
      image: postgres:15
      container_name: pulse-postgres-primary
      ports:
        - "5432:5432"
      # ... configuration
    
    postgres-replica:
      image: postgres:15  
      container_name: pulse-postgres-replica
      ports:
        - "5433:5432"
      # ... configuration
  ```

#### **Task 1.2: PostgreSQL Configuration**
- [ ] **Create `docker/postgres/primary/postgresql.conf`**
  - [ ] Enable WAL replication (`wal_level = replica`)
  - [ ] Configure replication slots (`max_replication_slots = 3`)
  - [ ] Set connection limits (`max_connections = 100`)

- [ ] **Create `docker/postgres/primary/pg_hba.conf`**
  - [ ] Allow replication connections
  - [ ] Configure authentication for replica user

#### **Task 1.3: Start Database Infrastructure**
- [ ] **Launch database containers**
  ```bash
  docker-compose -f docker-compose.db.yml up -d
  ```
- [ ] **Verify primary database is running**
  ```bash
  docker logs pulse-postgres-primary
  psql -h localhost -p 5432 -U postgres -d pulse_db -c "SELECT version();"
  ```
- [ ] **Verify replica is replicating**
  ```bash
  docker logs pulse-postgres-replica
  psql -h localhost -p 5433 -U postgres -d pulse_db -c "SELECT pg_is_in_recovery();"
  ```

#### **Task 1.4: Test Replication**
- [ ] **Run the migration --rollback-to 000 and --apply-all to cleanup database**

- [ ] **Verify data appears in replica**
  ```sql
  -- On replica (port 5433)
  SELECT * FROM clients WHERE name = 'WEX';
  ```
- [ ] **Measure replication lag**
  ```sql
  -- On primary
  SELECT pg_current_wal_lsn();
  -- On replica  
  SELECT pg_last_wal_replay_lsn();
  ```

---

### 🔧 **PHASE 2: Application Code Changes (Days 3-4)**

#### **Task 2.1: Update Configuration**
- [ ] **Update `.env` file with replica and connection pool settings**
  ```bash
  # Primary Database Configuration
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5432
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=pulse
  POSTGRES_DATABASE=pulse_db

  # Read Replica Configuration
  POSTGRES_REPLICA_HOST=localhost
  POSTGRES_REPLICA_PORT=5433
  # Uses same user/password/database as primary

  # Connection Pool Settings (Primary) - Optimized for Enterprise
  DB_POOL_SIZE=20                    # Up from 5
  DB_MAX_OVERFLOW=30                 # Up from 10
  DB_POOL_TIMEOUT=60                 # Up from 30
  DB_POOL_RECYCLE=3600              # Keep existing

  # Connection Pool Settings (Replica) - Optimized for Read Operations
  DB_REPLICA_POOL_SIZE=15           # Smaller for read operations
  DB_REPLICA_MAX_OVERFLOW=20        # Less overflow needed for reads
  DB_REPLICA_POOL_TIMEOUT=30        # Faster timeout for read queries

  # Feature Flags for Gradual Rollout
  USE_READ_REPLICA=true             # Enable/disable replica usage
  REPLICA_FALLBACK_ENABLED=true     # Fallback to primary if replica fails
  ```
- [ ] **Update `.env.example` with same settings and documentation**

#### **Task 2.2: Backend Service Changes**
- [ ] **Update `services/backend-service/app/core/config.py`**
  - [ ] Add replica connection string properties (reading from environment)
  - [ ] Add connection pool configuration (reading from environment):
    ```python
    # Read Replica Configuration
    POSTGRES_REPLICA_HOST: Optional[str] = Field(default=None, env="POSTGRES_REPLICA_HOST")
    POSTGRES_REPLICA_PORT: int = Field(default=5432, env="POSTGRES_REPLICA_PORT")

    # Connection Pool Settings (Primary)
    DB_POOL_SIZE: int = Field(default=5, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=10, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")

    # Connection Pool Settings (Replica)
    DB_REPLICA_POOL_SIZE: int = Field(default=5, env="DB_REPLICA_POOL_SIZE")
    DB_REPLICA_MAX_OVERFLOW: int = Field(default=10, env="DB_REPLICA_MAX_OVERFLOW")
    DB_REPLICA_POOL_TIMEOUT: int = Field(default=30, env="DB_REPLICA_POOL_TIMEOUT")

    # Feature Flags
    USE_READ_REPLICA: bool = Field(default=False, env="USE_READ_REPLICA")
    REPLICA_FALLBACK_ENABLED: bool = Field(default=True, env="REPLICA_FALLBACK_ENABLED")
    ```
  
- [ ] **Create `services/backend-service/app/core/database_router.py`**
  - [ ] Implement `DatabaseRouter` class
  - [ ] Add query routing logic
  - [ ] Add health monitoring

- [ ] **Update `services/backend-service/app/core/database.py`**
  - [ ] Add replica engine initialization
  - [ ] Implement `get_read_session()` and `get_write_session()`
  - [ ] Add specialized session context managers

#### **Task 2.3: ETL Service Changes**
- [ ] **Update `services/etl-service/app/core/config.py`**
  - [ ] Add replica configuration (same environment variables as backend)
  - [ ] Copy the same Field definitions from backend service config
  
- [ ] **Update `services/etl-service/app/core/database.py`**
  - [ ] Add replica support (ETL primarily uses primary)
  - [ ] Implement chunked session management
  - [ ] Add async yielding helpers

#### **Task 2.4: Query Routing Implementation**
- [ ] **Identify read-only queries in backend service**
  - [ ] Dashboard data endpoints
  - [ ] Analytics queries
  - [ ] Report generation
  
- [ ] **Route appropriate queries to replica**
  ```python
  # Example: Dashboard queries use replica
  @router.get("/pull-requests")
  async def get_pull_requests():
      with get_read_session() as session:
          # Query goes to replica
  ```

- [ ] **Ensure write operations use primary**
  ```python
  # Example: User management uses primary
  @router.post("/users")
  async def create_user():
      with get_write_session() as session:
          # Write goes to primary
  ```

---

### 🧪 **PHASE 3: Testing & Validation (Days 5-6)**

#### **Task 3.1: Unit Testing**
- [ ] **Test database router functionality**
  ```python
  def test_read_queries_use_replica():
      # Verify read operations route to replica
  
  def test_write_queries_use_primary():
      # Verify write operations route to primary
  ```

- [ ] **Test connection pool behavior**
  - [ ] Verify pool sizes are correct
  - [ ] Test connection exhaustion scenarios
  - [ ] Verify timeout behavior

#### **Task 3.2: Integration Testing**
- [ ] **Test full ETL cycle**
  - [ ] Run GitHub job with replica setup
  - [ ] Run Jira job with replica setup
  - [ ] Verify data consistency between primary and replica
  
- [ ] **Test user workflows**
  - [ ] Login/authentication
  - [ ] Dashboard loading
  - [ ] Admin operations
  - [ ] Settings management

#### **Task 3.3: Performance Testing**
- [ ] **Simulate heavy ETL load**
  ```bash
  # Run GitHub job while monitoring UI responsiveness
  # Measure dashboard response times during ETL
  ```
  
- [ ] **Monitor connection pools**
  - [ ] Check pool utilization during heavy operations
  - [ ] Verify no connection exhaustion
  - [ ] Monitor query response times

#### **Task 3.4: Failover Testing**
- [ ] **Test replica failure scenario**
  ```bash
  # Stop replica container
  docker stop pulse-postgres-replica
  # Verify reads fallback to primary
  ```
  
- [ ] **Test primary failure scenario**
  ```bash
  # Stop primary container (should fail gracefully)
  docker stop pulse-postgres-primary
  ```

---

### 🚀 **PHASE 4: Deployment & Monitoring (Days 7-8)**

#### **Task 4.1: Production Preparation**
- [ ] **Update production docker-compose.yml**
  - [ ] Add replica configuration
  - [ ] Update service dependencies
  
- [ ] **Create monitoring scripts**
  ```python
  # Monitor replication lag
  # Monitor connection pool utilization
  # Alert on replica failures
  ```

#### **Task 4.2: Gradual Rollout**
- [ ] **Deploy to staging environment**
  - [ ] Test full functionality
  - [ ] Run performance benchmarks
  - [ ] Verify monitoring works
  
- [ ] **Feature flag implementation**
  ```python
  # Allow toggling replica usage on/off
  USE_REPLICA_FOR_READS = os.getenv('USE_REPLICA_FOR_READS', 'true')
  ```

#### **Task 4.3: Production Deployment**
- [ ] **Deploy during low-traffic window**
- [ ] **Monitor key metrics**
  - [ ] Response times
  - [ ] Error rates  
  - [ ] Connection pool utilization
  - [ ] Replication lag
  
- [ ] **Verify user experience**
  - [ ] Test all major workflows
  - [ ] Confirm performance improvements
  - [ ] Check for any regressions

---

### 📊 **Post-Migration Validation**

#### **Success Criteria Verification**
- [ ] **Performance Metrics**
  - [ ] UI responsive during ETL operations ✓
  - [ ] Dashboard loads < 2 seconds during ETL ✓
  - [ ] Connection pool utilization < 80% ✓
  - [ ] Replication lag < 1 second ✓

- [ ] **Functional Requirements**
  - [ ] All features work identically ✓
  - [ ] No data loss or corruption ✓
  - [ ] Graceful replica failover ✓
  - [ ] Monitoring and alerting active ✓

#### **Documentation Updates**
- [ ] **Update README files**
- [ ] **Update deployment documentation**
- [ ] **Create troubleshooting guide**
- [ ] **Document monitoring procedures**

---

### 🚨 **Rollback Plan**

#### **If Issues Arise**
1. **Fix issues - everything is already protected for any needed rollback**
---

This checklist ensures a systematic, safe implementation of the replica strategy with clear validation steps and rollback procedures.
