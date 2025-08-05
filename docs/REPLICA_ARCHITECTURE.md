# 🔄 Pulse Platform - Replica Architecture Guide

## 📋 **Overview**

The Pulse Platform implements PostgreSQL streaming replication to provide enterprise-grade performance, scalability, and reliability. This architecture separates read and write operations across primary and replica databases for optimal resource utilization.

## 🏗️ **Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                           │
│                                                                 │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │  Backend Service│              │  ETL Service    │          │
│  │  (Port 3001)    │              │  (Port 8000)    │          │
│  │                 │              │                 │          │
│  │ Database Router │              │ Database Router │          │
│  └─────────────────┘              └─────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Router Layer                       │
│                                                                 │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │  Write Session  │              │  Read Session   │          │
│  │  (Primary Only) │              │ (Replica First) │          │
│  └─────────────────┘              └─────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌─────────────────┐                  ┌─────────────────┐
│  PRIMARY DB     │─────────────────►│  REPLICA DB     │
│  Port: 5432     │  WAL Streaming   │  Port: 5433     │
│                 │                  │                 │
│ • User Mgmt     │                  │ • Analytics     │
│ • Admin Ops     │                  │ • Dashboards    │
│ • Job Control   │                  │ • Reports       │
│ • Auth/Sessions │                  │ • Metrics       │
│ • All Writes    │                  │ • Read-Only     │
└─────────────────┘                  └─────────────────┘
```

## ⚙️ **Configuration**

### **Environment Variables**

```bash
# Root-level .env file
# Primary Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pulse
POSTGRES_DATABASE=pulse_db

# Replica Database
POSTGRES_REPLICA_HOST=localhost
POSTGRES_REPLICA_PORT=5433

# Feature Flags
USE_READ_REPLICA=true
REPLICA_FALLBACK_ENABLED=true

# Connection Pool Settings
DB_POOL_SIZE=20                    # Primary pool
DB_MAX_OVERFLOW=30
DB_REPLICA_POOL_SIZE=15           # Replica pool
DB_REPLICA_MAX_OVERFLOW=20
```

### **Docker Compose Setup**

```bash
# Start replica infrastructure
docker-compose -f docker-compose.db.yml up -d

# Verify containers are running
docker ps | grep pulse-postgres

# Check replication status
docker exec pulse-postgres-replica psql -U postgres -d pulse_db -c "SELECT pg_is_in_recovery();"
```

## 🔀 **Query Routing Rules**

### **Primary Database Operations**
- **User Authentication & Sessions**: Login, logout, session management
- **User Management**: Create, update, delete users
- **Admin Operations**: Configuration changes, settings updates
- **Job Control**: Start, stop, pause, resume ETL jobs
- **Client Management**: Client settings, logo uploads
- **All Write Operations**: INSERT, UPDATE, DELETE statements

### **Replica Database Operations**
- **Dashboard Metrics**: DORA metrics, KPI calculations
- **Analytics Queries**: Historical data analysis, trend reports
- **Data Visualization**: Chart data, graph generation
- **Export Operations**: CSV exports, report generation
- **Read-Only Queries**: Complex JOINs, aggregations

## 💻 **Development Usage**

### **Backend Service Examples**

```python
# ✅ CORRECT: User management (write operation)
@router.post("/users")
async def create_user(user_data: UserCreateRequest):
    database = get_database()
    with database.get_write_session_context() as session:
        new_user = User(...)
        session.add(new_user)
        # Automatic commit

# ✅ CORRECT: User listing (read operation)
@router.get("/users")
async def get_users():
    database = get_database()
    with database.get_read_session_context() as session:
        users = session.query(User).filter_by(client_id=client_id).all()

# ✅ CORRECT: System statistics (analytics)
@router.get("/system/stats")
async def get_system_stats():
    database = get_database()
    with database.get_analytics_session_context() as session:
        stats = session.execute(complex_analytics_query)
```

### **ETL Service Examples**

```python
# ✅ CORRECT: Job control (write operation)
@router.post("/jobs/{job_id}/start")
async def start_job(job_id: int):
    database = get_database()
    with database.get_write_session_context() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        job.status = "RUNNING"

# ✅ CORRECT: Job status queries (read operation)
@router.get("/jobs/status")
async def get_job_status():
    database = get_database()
    with database.get_read_session_context() as session:
        jobs = session.query(Job).filter_by(client_id=client_id).all()

# ✅ CORRECT: Bulk data processing (chunked writes)
async def process_github_data(prs_data):
    database = get_database()
    processor = ChunkedBulkProcessor(chunk_size=100)
    
    async def process_chunk(session, pr_chunk):
        for pr_data in pr_chunk:
            pr = PullRequest(...)
            session.add(pr)
    
    await processor.process_bulk_data(prs_data, process_chunk)
```

## 🔧 **Management Commands**

### **Database Operations**

```bash
# Start replica infrastructure
docker-compose -f docker-compose.db.yml up -d

# Stop databases (keeps data)
docker-compose -f docker-compose.db.yml down

# Reset databases (DELETES ALL DATA!)
docker-compose -f docker-compose.db.yml down -v

# Check container status
docker ps | grep pulse-postgres
```

### **Connection Testing**

```bash
# Test primary database
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT 'PRIMARY' as db_type;"

# Test replica database
docker exec pulse-postgres-replica psql -U postgres -d pulse_db -c "SELECT 'REPLICA' as db_type, pg_is_in_recovery();"

# Test replication lag
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT pg_current_wal_lsn();"
docker exec pulse-postgres-replica psql -U postgres -d pulse_db -c "SELECT pg_last_wal_replay_lsn();"
```

### **External Tool Connections**

**DBeaver/pgAdmin Connection Settings:**

**Primary Database (Read/Write):**
- Host: `localhost`
- Port: `5432`
- Database: `pulse_db`
- Username: `postgres`
- Password: `pulse`

**Replica Database (Read-Only):**
- Host: `localhost`
- Port: `5433`
- Database: `pulse_db`
- Username: `postgres`
- Password: `pulse`

## 🚀 **Performance Benefits**

### **Connection Pool Optimization**
- **Primary Pool**: 20 base + 30 overflow connections (enterprise-grade)
- **Replica Pool**: 15 base + 20 overflow connections (read-optimized)
- **Intelligent Routing**: Automatic query distribution based on operation type

### **Scalability Improvements**
- **Read Load Distribution**: Analytics queries don't impact write performance
- **Concurrent Operations**: Dashboard updates don't block ETL operations
- **Resource Isolation**: Different workloads use appropriate database instances

### **Reliability Features**
- **Automatic Failover**: Read queries fall back to primary if replica unavailable
- **Health Monitoring**: Continuous replica status and lag monitoring
- **Data Consistency**: Near real-time replication via WAL streaming

## 🛡️ **Failover & Recovery**

### **Automatic Failover**
```python
# System automatically handles replica failures
with database.get_read_session_context() as session:
    # If replica is down, automatically uses primary
    data = session.query(Model).all()
```

### **Manual Failover Testing**
```bash
# Simulate replica failure
docker stop pulse-postgres-replica

# Application continues working (uses primary for reads)
# Test your application functionality

# Restore replica
docker start pulse-postgres-replica

# Application automatically starts using replica again
```

## 📊 **Monitoring & Troubleshooting**

### **Health Checks**
```bash
# Check replication status
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT * FROM pg_replication_slots;"

# Monitor connection pools
# (Available via application endpoints or logs)

# Check resource usage
docker stats pulse-postgres-primary pulse-postgres-replica
```

### **Common Issues**
1. **Replica Lag**: Monitor with `pg_current_wal_lsn()` vs `pg_last_wal_replay_lsn()`
2. **Connection Pool Exhaustion**: Monitor pool utilization metrics
3. **Failover Delays**: Check replica health monitoring frequency

## 🎯 **Best Practices**

1. **Use Appropriate Sessions**: Write operations → primary, read operations → replica
2. **Monitor Performance**: Track connection pool utilization and query performance
3. **Test Failover**: Regularly test replica failure scenarios
4. **Optimize Queries**: Use analytics sessions for complex read operations
5. **Chunk Large Operations**: Use ChunkedBulkProcessor for bulk data processing

This replica architecture provides enterprise-grade performance and reliability while maintaining simplicity for developers through intelligent query routing and automatic failover capabilities.
