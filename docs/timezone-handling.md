# Timezone Handling Strategy

## Overview

The Pulse Platform uses a **UTC-first approach** for all database operations to ensure data consistency across different timezones and deployments.

## Critical Rules

### 🚨 **NEVER use `datetime.now()` for database operations**
Always use `DateTimeHelper.now_utc()` instead.

### ✅ **Database Storage: UTC Only**
- All timestamps in the database are stored in UTC
- PostgreSQL is configured with `timezone = 'UTC'`
- All SQLAlchemy models use `default=func.now()` which respects PostgreSQL's UTC setting

### 🎯 **Display: Convert to User's Timezone**
- Use `DateTimeHelper.utc_to_central()` to convert UTC timestamps for display
- Frontend should handle timezone conversion for user interface

## Configuration

### Environment Variables
```bash
# Use UTC for consistency with database
SCHEDULER_TIMEZONE=UTC
```

### PostgreSQL Configuration
```sql
-- In postgresql.conf
timezone = 'UTC'
```

## Code Examples

### ✅ Correct: Database Operations
```python
from app.core.utils import DateTimeHelper

# For database timestamps
current_time = DateTimeHelper.now_utc()
user.last_login_at = current_time

# For monthly calculations
now = DateTimeHelper.now_utc()
current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
```

### ✅ Correct: Display Operations
```python
# Convert UTC to Central Time for display
display_time = DateTimeHelper.utc_to_central(user.last_login_at)
```

### ❌ Incorrect: Mixed Timezone Usage
```python
# DON'T DO THIS - causes data inconsistency
now = datetime.now()  # Uses system timezone
user.last_login_at = now
```

## Database Models

All models inherit timezone-aware defaults:

```python
class BaseEntity:
    created_at = Column(DateTime, default=func.now())  # Uses PostgreSQL UTC
    last_updated_at = Column(DateTime, default=func.now())  # Uses PostgreSQL UTC
```

## Migration Strategy

### Existing Data
- All existing timestamps are already in UTC (PostgreSQL default)
- No data migration required

### Application Updates
- Updated `DateTimeHelper.now_utc()` with clear documentation
- Added `DateTimeHelper.utc_to_central()` for display conversion
- Fixed monthly growth calculation to use UTC

## Testing

### Verify Timezone Consistency
```python
# Test that database operations use UTC
from app.core.utils import DateTimeHelper
import datetime

# These should be nearly identical (within seconds)
db_time = DateTimeHelper.now_utc()
pg_time = session.execute("SELECT NOW()").scalar()

assert abs((db_time - pg_time).total_seconds()) < 5
```

## Common Pitfalls

1. **Using `datetime.now()`** - Uses system timezone, not UTC
2. **Mixing timezone-aware and naive datetimes** - Causes comparison errors
3. **Assuming user's local timezone** - Users may be in different timezones
4. **Not converting for display** - Shows UTC times to users

## Best Practices

1. **Always use `DateTimeHelper.now_utc()`** for database operations
2. **Convert to user timezone** only for display purposes
3. **Document timezone assumptions** in code comments
4. **Test across timezones** during development
5. **Use consistent timezone** in all environments (UTC)

## Impact Areas Fixed

- ✅ User session timestamps
- ✅ Monthly growth calculations  
- ✅ Job scheduling
- ✅ Data import timestamps
- ✅ Analytics calculations
- ✅ Audit trail timestamps

## Future Considerations

- Add user timezone preference to user profile
- Implement frontend timezone detection
- Add timezone conversion utilities for API responses
- Consider timezone-aware date pickers in UI
