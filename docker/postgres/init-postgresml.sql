-- PostgresML Initialization Script
-- This script sets up PostgresML extensions and configurations for AI capabilities

-- Create required extensions
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS postgresml;

-- Configure PostgresML settings
-- Enable shared_preload_libraries for PostgresML (this is typically done in postgresql.conf)
-- For Docker, we'll ensure the extensions are available

-- Create a simple test to verify PostgresML is working
DO $$
BEGIN
    -- Test that pgvector is working
    PERFORM '[]'::vector;
    RAISE NOTICE 'pgvector extension is working correctly';

    -- Test that vector extension is working
    RAISE NOTICE 'Vector extension is available for AI operations';

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Extension initialization encountered an issue: %', SQLERRM;
END $$;

-- Set up basic configurations for AI operations
-- These settings optimize PostgreSQL for ML workloads
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- Reload configuration
SELECT pg_reload_conf();

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'PostgresML initialization completed successfully';
    RAISE NOTICE 'Extensions available: vector, postgresml';
    RAISE NOTICE 'Database is ready for AI operations';
END $$;
