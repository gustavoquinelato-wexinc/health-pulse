# ETL Service Testing Guide

## Overview

This guide covers the testing tools and utilities available for the ETL service, including debugging tools, performance testing, and database management utilities.

## Testing Scripts

### 1. Jira Jobs Testing (`utils/test_jira_jobs.py`)

A comprehensive debugging tool for Jira job execution with database reset capabilities.

#### Features

- **Environment Testing**: Validates configuration and credentials
- **Connection Testing**: Tests Jira API connectivity
- **Database Reset**: Complete database reset and integration setup
- **Step-by-Step Debugging**: Interactive debugging of individual job steps
- **Full Job Debugging**: Complete job execution with detailed monitoring
- **Scheduler Testing**: Validates scheduler configuration

#### Usage Examples

```bash
# 🚀 COMPLETE TEST:
python utils/test_jira_jobs.py --all             # ⚠️  Reset DB + run full job execution

# 🔗 CONNECTION TESTING:
python utils/test_jira_jobs.py --test-connection # Test Jira API connection
python utils/test_jira_jobs.py --test-scheduler  # Test scheduler configuration

# 🐛 JOB DEBUGGING:
python utils/test_jira_jobs.py --step-by-step    # Interactive step-by-step debugging
python utils/test_jira_jobs.py --debug-job       # Full job with monitoring
python utils/test_jira_jobs.py --debug-job --debug  # Full job with verbose logging
```

#### Complete Test Workflow (`--all` option)

**⚠️ WARNING: This is a DESTRUCTIVE operation that performs a complete end-to-end test!**

The `--all` option performs a complete test workflow in three steps:

**STEP 1: Database Reset & Setup**
1. **Drops all tables** - All existing data is permanently deleted
2. **Recreates all tables** - Fresh schema is created
3. **Inserts integration details** - Configured integrations are added

**STEP 2: Environment & Connection Validation**
4. **Tests environment configuration** - Validates all required settings
5. **Tests Jira API connection** - Verifies connectivity and permissions
6. **Tests database connection** - Ensures database is accessible

**STEP 3: Full Job Execution**
7. **Runs complete Jira job** - Executes full data extraction and processing
8. **Provides detailed monitoring** - Shows progress and performance metrics

**What gets inserted:**
- **Jira integration** (if `JIRA_URL`, `JIRA_USERNAME`, `JIRA_TOKEN` are configured)
- **GitHub integration** (if `GITHUB_TOKEN` is configured)
- **Aha! integration** (if `AHA_TOKEN` and `AHA_URL` are configured)
- **Azure DevOps integration** (if `AZDO_TOKEN` and `AZDO_URL` are configured)

**Complete Workflow:**
- After successful database reset, automatically runs full job execution
- Provides step-by-step progress monitoring
- Shows detailed results for each phase
- Stops execution if any step fails

**Safety Features:**
- Requires explicit confirmation (user must type 'YES')
- Shows warning about data loss
- Validates environment configuration first
- Uses encrypted token storage

### 2. Performance Testing (`utils/test_bulk_performance.py`)

Tests and compares bulk insert performance improvements.

#### Features

- **Bulk vs Individual Insert Comparison**: Measures performance differences
- **Configurable Test Sizes**: Test with different record counts
- **Detailed Metrics**: Timing and performance statistics
- **Automatic Cleanup**: Removes test data after completion

#### Usage Examples

```bash
# Test with default settings (100 records)
python utils/test_bulk_performance.py

# Test with specific number of records
python utils/test_bulk_performance.py --records 1000

# Test only bulk inserts (skip slow individual tests)
python utils/test_bulk_performance.py --skip-individual

# Verbose output with detailed logging
python utils/test_bulk_performance.py --verbose
```

#### Performance Results

Typical results show **15-30x performance improvement** with bulk inserts:

```
ISSUETYPES:
  Bulk inserts:       1.514 seconds
  
PROJECTS:
  Bulk inserts:       1.616 seconds
  
STATUSES:
  Bulk inserts:       2.219 seconds
```

## Development Workflow

### 1. Complete End-to-End Test

```bash
# Complete test: reset database + run full job execution
python utils/test_jira_jobs.py --all

# Or just verify connections without job execution
python utils/test_jira_jobs.py --test-connection
```

### 2. Development and Debugging

```bash
# Interactive debugging for development
python utils/test_jira_jobs.py --step-by-step

# Full job testing
python utils/test_jira_jobs.py --debug-job --debug
```

### 3. Performance Testing

```bash
# Test performance improvements
python utils/test_bulk_performance.py --records 100

# Compare with larger datasets
python utils/test_bulk_performance.py --records 1000 --skip-individual
```

### 4. Production Readiness

```bash
# Final validation
python utils/test_jira_jobs.py --test-connection
python utils/test_jira_jobs.py --test-scheduler

# Run actual job
python -m app.jobs.jira_job --dry-run
```

## Troubleshooting

### Common Issues

#### 1. Environment Configuration

**Problem**: Missing or invalid configuration
**Solution**: 
```bash
python utils/test_jira_jobs.py --test-connection
```
Check the output for missing environment variables.

#### 2. Database Connection Issues

**Problem**: Cannot connect to database
**Solution**:
- Verify database credentials in `.env`
- Check network connectivity
- Ensure database service is running

#### 3. Jira API Issues

**Problem**: Jira connection failures
**Solution**:
- Verify Jira URL, username, and token
- Check network access to Jira instance
- Validate token permissions

#### 4. Performance Issues

**Problem**: Slow job execution
**Solution**:
```bash
# Test performance
python utils/test_bulk_performance.py

# Debug step-by-step
python utils/test_jira_jobs.py --step-by-step
```

### Debug Logging

Enable debug logging for detailed troubleshooting:

```bash
# Debug mode for any script
python utils/test_jira_jobs.py --debug-job --debug
python utils/test_bulk_performance.py --verbose
```

Logs are written to:
- Console output
- `logs/test_jira_jobs.log` (for test script)
- Application logs (for job execution)

## Best Practices

### 1. Development Environment

- Always use `--all` to reset database when starting fresh
- Use `--step-by-step` for debugging specific issues
- Test performance changes with `test_bulk_performance.py`

### 2. Testing Changes

1. **Complete test**: `python utils/test_jira_jobs.py --all` (resets DB + runs job)
2. **Debug specific issues**: `python utils/test_jira_jobs.py --step-by-step`
3. **Performance test**: `python utils/test_bulk_performance.py`
4. **Connection only**: `python utils/test_jira_jobs.py --test-connection`

### 3. Production Deployment

- Never use `--all` in production (it deletes all data!)
- Use dry-run mode for validation: `python -m app.jobs.jira_job --dry-run`
- Monitor performance with regular testing

## Safety Considerations

### Database Reset Safety

The `--all` option is designed for development environments:

- **Requires explicit confirmation** - User must type 'YES'
- **Shows clear warnings** about data loss
- **Not intended for production** use
- **Backs up nothing** - all data is permanently lost

### Production Safety

- Use separate databases for development and production
- Never run `--all` against production database
- Test all changes in development environment first
- Use proper backup procedures for production data

## Integration with CI/CD

### Automated Testing

```bash
# In CI pipeline
python utils/test_jira_jobs.py --test-connection
python utils/test_bulk_performance.py --records 10 --skip-individual
python -m app.jobs.jira_job --dry-run
```

### Environment Setup

```bash
# For fresh test environments
python utils/test_jira_jobs.py --all
```

This ensures consistent test environments across different systems.
