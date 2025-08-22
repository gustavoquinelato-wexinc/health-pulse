# Pulse Platform Database Restore

This folder contains a complete database dump and restore scripts for the Pulse Platform with all data included.

## 📦 What's Included

### Files
- `pulse_platform_full_dump.backup` - Complete binary database dump with all constraints
- `create_dump.bat` - Create new binary dump from pulse_db database
- `restore_phack.bat` - Restore to `phack` database
- `verify_restore.bat` - Verify restore was successful
- `README.md` - This documentation

### Database Contents
- ✅ **All database schema and tables**
- ✅ **All user accounts and permissions**
- ✅ **All Jira issues (~33,000 issues with changelogs)**
- ✅ **All GitHub pull requests and data**
- ✅ **All job schedules and configurations**
- ✅ **All client settings and integrations**
- ✅ **All foreign keys, unique constraints, and indexes**
- ✅ **All triggers and sequences**


## 🔧 Restore Process
```bash
# 1. Ensure PostgreSQL is up and running
docker-compose -f docker-compose.db.yml up -d

# 2. if database already exists, run migration rollback
python .\services\backend\scripts\migration_runner.py --rollback-to 000

# 3. Run restore_phack.bat
.\restore_phack.bat

# 3. Restart dcoker
Restart containers in docker;
Replica will automatically get refreshed after it.
```
