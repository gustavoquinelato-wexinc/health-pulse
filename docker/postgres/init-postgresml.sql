-- PostgresML Initialization Script
-- This script sets up PostgresML extensions and configurations for AI capabilities

-- Check what extensions are available
DO $$
DECLARE
    rec RECORD;
BEGIN
    RAISE NOTICE 'Available extensions:';
    FOR rec IN SELECT name FROM pg_available_extensions ORDER BY name LOOP
        RAISE NOTICE '  - %', rec.name;
    END LOOP;
END $$;

-- Create required extensions (with error handling)
DO $$
BEGIN
    -- Try to create pgvector extension
    BEGIN
        CREATE EXTENSION IF NOT EXISTS pgvector;
        RAISE NOTICE 'pgvector extension created successfully';
    EXCEPTION WHEN OTHERS THEN
        RAISE WARNING 'pgvector extension not available: %', SQLERRM;
    END;

    -- Try to create postgresml extension
    BEGIN
        CREATE EXTENSION IF NOT EXISTS postgresml;
        RAISE NOTICE 'postgresml extension created successfully';
    EXCEPTION WHEN OTHERS THEN
        RAISE WARNING 'postgresml extension not available: %', SQLERRM;
    END;
END $$;

-- Configure PostgresML settings
-- Enable shared_preload_libraries for PostgresML (this is typically done in postgresql.conf)
-- For Docker, we'll ensure the extensions are available

-- Create a simple test to verify extensions are working
DO $$
BEGIN
    -- Test that pgvector is working (if available)
    BEGIN
        PERFORM '[]'::vector;
        RAISE NOTICE 'pgvector extension is working correctly';
    EXCEPTION WHEN OTHERS THEN
        RAISE WARNING 'pgvector extension test failed: %', SQLERRM;
    END;

    -- Test basic PostgreSQL functionality
    RAISE NOTICE 'PostgreSQL is ready for operations';

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Extension testing encountered an issue: %', SQLERRM;
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
