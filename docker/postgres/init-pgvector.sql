-- pgvector Initialization Script
-- This script sets up pgvector extension for AI vector operations

-- Create required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Test that pgvector is working
DO $$
BEGIN
    -- Test that vector extension is working
    PERFORM '[0,1,2]'::vector;
    RAISE NOTICE 'pgvector extension is working correctly';
    RAISE NOTICE 'Database is ready for AI vector operations';

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Extension initialization encountered an issue: %', SQLERRM;
END $$;

-- Set up basic configurations optimized for vector operations
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
    RAISE NOTICE 'pgvector initialization completed successfully';
    RAISE NOTICE 'Extensions available: vector';
    RAISE NOTICE 'Database is ready for AI operations with vector similarity search';
END $$;
