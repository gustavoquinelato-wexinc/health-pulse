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

# Debug: Show network connectivity
echo "🔍 Debugging network connectivity..."
echo "Primary host: $POSTGRES_PRIMARY_HOST"
echo "Primary port: $POSTGRES_PRIMARY_PORT"
echo "Replication user: $POSTGRES_REPLICATION_USER"
echo "Container IP: $(hostname -i)"

# Test basic connectivity
echo "🌐 Testing basic connectivity to primary..."
# Test connectivity using pg_isready instead of nc
if pg_isready -h "$POSTGRES_PRIMARY_HOST" -p "$POSTGRES_PRIMARY_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then
    echo "✅ Network connection to primary successful"
else
    echo "❌ Network connection to primary failed"
    exit 1
fi

# Test PostgreSQL connectivity
echo "🔍 Testing PostgreSQL connectivity..."
if pg_isready -h "$POSTGRES_PRIMARY_HOST" -p "$POSTGRES_PRIMARY_PORT" -U "$POSTGRES_USER"; then
    echo "✅ PostgreSQL connection test successful"
else
    echo "❌ PostgreSQL connection test failed"
fi

# Only set up replica if standby.signal doesn't exist (indicating it's not already a replica)
if [ ! -f "$PGDATA/standby.signal" ]; then
    echo "🧹 Setting up fresh replica..."

    # Stop PostgreSQL if running
    sudo -u postgres /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -m fast stop || true

    # Remove any existing data directory contents
    rm -rf "$PGDATA"/*

    # Create base backup from primary
    echo "📦 Creating base backup from primary..."

    # Set up .pgpass file for authentication
    echo "$POSTGRES_PRIMARY_HOST:$POSTGRES_PRIMARY_PORT:*:$POSTGRES_REPLICATION_USER:$POSTGRES_REPLICATION_PASSWORD" > ~/.pgpass
    chmod 600 ~/.pgpass

    # Try with password authentication first
    echo "🔐 Attempting connection with password authentication..."
    if ! PGPASSWORD="$POSTGRES_REPLICATION_PASSWORD" pg_basebackup \
        -h "$POSTGRES_PRIMARY_HOST" \
        -p "$POSTGRES_PRIMARY_PORT" \
        -U "$POSTGRES_REPLICATION_USER" \
        -D "$PGDATA" \
        -Fp \
        -Xs \
        -P \
        -R \
        -w; then

        echo "🔓 Password auth failed, trying trust authentication..."
        # If password auth fails, try without password (trust mode)
        pg_basebackup \
            -h "$POSTGRES_PRIMARY_HOST" \
            -p "$POSTGRES_PRIMARY_PORT" \
            -U "$POSTGRES_REPLICATION_USER" \
            -D "$PGDATA" \
            -Fp \
            -Xs \
            -P \
            -R
    fi

    # Create recovery configuration
    echo "⚙️ Configuring recovery settings..."
    cat >> "$PGDATA/postgresql.auto.conf" <<EOF
# Replica configuration
primary_conninfo = 'host=$POSTGRES_PRIMARY_HOST port=$POSTGRES_PRIMARY_PORT user=$POSTGRES_REPLICATION_USER password=$POSTGRES_REPLICATION_PASSWORD application_name=replica'
primary_slot_name = 'replica_slot'
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
