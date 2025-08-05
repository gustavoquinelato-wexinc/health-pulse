#!/bin/bash
# PostgreSQL Replica Database - Setup Script

set -e

echo "🔧 Setting up PostgreSQL replica..."

# Wait for primary to be ready
echo "⏳ Waiting for primary database to be ready..."
until pg_isready -h "$POSTGRES_PRIMARY_HOST" -p "$POSTGRES_PRIMARY_PORT" -U "$POSTGRES_USER"; do
    echo "Primary database is not ready yet. Waiting..."
    sleep 2
done

echo "✅ Primary database is ready!"

# Only set up replica if data directory is empty
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "🧹 Setting up fresh replica..."

    # Remove any existing data directory contents
    rm -rf "$PGDATA"/*

    # Create base backup from primary
    echo "📦 Creating base backup from primary..."
    PGPASSWORD="$POSTGRES_REPLICATION_PASSWORD" pg_basebackup \
        -h "$POSTGRES_PRIMARY_HOST" \
        -p "$POSTGRES_PRIMARY_PORT" \
        -U "$POSTGRES_REPLICATION_USER" \
        -D "$PGDATA" \
        -Fp \
        -Xs \
        -P \
        -R \
        -W

    # Create recovery configuration
    echo "⚙️ Configuring recovery settings..."
    cat >> "$PGDATA/postgresql.auto.conf" <<EOF
# Replica configuration
primary_conninfo = 'host=$POSTGRES_PRIMARY_HOST port=$POSTGRES_PRIMARY_PORT user=$POSTGRES_REPLICATION_USER password=$POSTGRES_REPLICATION_PASSWORD application_name=replica'
primary_slot_name = 'replica_slot'
promote_trigger_file = '/tmp/promote_replica'
hot_standby = on
EOF

    # Create standby.signal file to indicate this is a standby server
    touch "$PGDATA/standby.signal"

    echo "✅ Replica setup completed!"
    echo "📊 Replica will connect to primary at $POSTGRES_PRIMARY_HOST:$POSTGRES_PRIMARY_PORT"
    echo "🔄 Using replication slot: replica_slot"
    echo "🎯 Ready to start in hot standby mode"
else
    echo "✅ Replica already configured, skipping setup"
fi
