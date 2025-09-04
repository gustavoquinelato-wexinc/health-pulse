#!/bin/bash
# PostgreSQL Primary Database - Replication Initialization Script

set -e

echo "🔧 Initializing replication on primary database..."

# Create replication user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create replication user if it doesn't exist
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'replicator') THEN
            CREATE ROLE replicator WITH REPLICATION PASSWORD 'replicator_password' LOGIN;
            GRANT CONNECT ON DATABASE $POSTGRES_DB TO replicator;
            GRANT USAGE ON SCHEMA public TO replicator;
            GRANT SELECT ON ALL TABLES IN SCHEMA public TO replicator;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO replicator;
            
            RAISE NOTICE '✅ Replication user "replicator" created successfully';
        ELSE
            RAISE NOTICE '✅ Replication user "replicator" already exists';
        END IF;
    END
    \$\$;

    -- Create replication slot for replica
    SELECT pg_create_physical_replication_slot('replica_slot');
    
    -- Show replication status
    SELECT slot_name, slot_type, active, restart_lsn FROM pg_replication_slots;
EOSQL

# Create archive directory
mkdir -p /var/lib/postgresql/archive
chown postgres:postgres /var/lib/postgresql/archive
chmod 700 /var/lib/postgresql/archive

echo "✅ Primary database replication setup completed!"
echo "📊 Replication slot 'replica_slot' created"
echo "📁 Archive directory created at /var/lib/postgresql/archive"
