#!/bin/bash
set -e

# Custom PostgresML entrypoint that avoids the double-start issue
echo "Starting PostgresML (PostgreSQL only, no dashboard)"

# Kill any existing PostgreSQL processes to avoid conflicts
pkill -f postgres || true
pkill -f postmaster || true

# Clean up any existing lock files
rm -f /var/run/postgresql/.s.PGSQL.5432.lock
rm -f /tmp/.s.PGSQL.5432.lock

# Set PostgreSQL environment
export PGDATA="${PGDATA:-/var/lib/postgresql/data}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-postgres}"

# Ensure data directory exists and has correct permissions
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

# Initialize database if needed
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL database with UTF-8 encoding..."
    # Create password file
    echo "$POSTGRES_PASSWORD" > /tmp/pwfile
    sudo -u postgres /usr/lib/postgresql/15/bin/initdb -D "$PGDATA" --username="$POSTGRES_USER" --pwfile=/tmp/pwfile --auth-local=trust --auth-host=md5 --encoding=UTF8 --locale=C.UTF-8
    rm /tmp/pwfile

    # Configure PostgreSQL
    echo "host all all all md5" >> "$PGDATA/pg_hba.conf"
    echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf"
    echo "port = 5432" >> "$PGDATA/postgresql.conf"

    # Start PostgreSQL temporarily for setup
    sudo -u postgres /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -w start

    # Create database if specified with UTF-8 encoding
    if [ "$POSTGRES_DB" != "postgres" ]; then
        sudo -u postgres /usr/lib/postgresql/15/bin/createdb "$POSTGRES_DB" --encoding=UTF8 --locale=C.UTF-8 --template=template0
    fi

    # Create replication user if specified
    if [ -n "$POSTGRES_REPLICATION_USER" ] && [ -n "$POSTGRES_REPLICATION_PASSWORD" ]; then
        sudo -u postgres /usr/lib/postgresql/15/bin/psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
            CREATE USER $POSTGRES_REPLICATION_USER REPLICATION LOGIN CONNECTION LIMIT 100 ENCRYPTED PASSWORD '$POSTGRES_REPLICATION_PASSWORD';
EOSQL
    fi

    # Run initialization scripts
    for f in /docker-entrypoint-initdb.d/*; do
        case "$f" in
            *.sh)     echo "$0: running $f"; . "$f" ;;
            *.sql)    echo "$0: running $f"; sudo -u postgres /usr/lib/postgresql/15/bin/psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$f"; echo ;;
            *.sql.gz) echo "$0: running $f"; gunzip -c "$f" | sudo -u postgres /usr/lib/postgresql/15/bin/psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"; echo ;;
            *)        echo "$0: ignoring $f" ;;
        esac
        echo
    done

    # Stop temporary PostgreSQL
    sudo -u postgres /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -m fast -w stop
fi

# Start PostgreSQL in foreground as postgres user
echo "Starting PostgreSQL server in foreground..."
exec sudo -u postgres /usr/lib/postgresql/15/bin/postgres -D "$PGDATA"
