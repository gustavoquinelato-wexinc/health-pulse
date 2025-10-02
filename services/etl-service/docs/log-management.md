# Log Management System

## 🎯 Overview

The ETL Service includes a comprehensive log management system with structured logging, colorful console output, and a modern web interface for viewing, managing, and maintaining log files.

## 🌈 Structured Logging Features

### **Windows-Compatible Structured Logging**
- **Colorful Console Output**: Beautiful colored logs with structured data using structlog
- **Windows Compatible**: No Unicode emoji characters to prevent encoding errors
- **Categorized Prefixes**: Clear prefixes like `[HTTP]`, `[WS]`, `[AUTH]`, `[JIRA]`, `[GITHUB]` for easy filtering
- **Rich Context Data**: Structured key-value pairs for detailed debugging
- **Real-time Streaming**: Live log updates with WebSocket connections

### **Log Categories & Prefixes**
```
[HTTP]    - HTTP requests and responses
[WS]      - WebSocket connections and messages
[AUTH]    - Authentication and authorization
[JIRA]    - Jira job execution and API calls
[GITHUB]  - GitHub job execution and API calls
[ORCH]    - Orchestrator operations
[ETL]     - ETL service lifecycle events
[SCHED]   - Scheduler operations
[COLOR]   - Color schema management
[BULK]    - Bulk database operations
[ERROR]   - Error conditions and exceptions
[TEST]    - Testing and debugging messages
```

### **Example Log Output**
```
2025-09-04T01:19:52.225555Z [info] [HTTP] Request [app.core.logging_config] method=GET url=http://localhost:8000/ headers_count=15
2025-09-04T01:19:52.226255Z [info] [WS] Connected [app.core.websocket_manager] job_name=Jira total_connections=1
2025-09-04T01:19:52.239316Z [info] [BULK] Processing 9 issuetypes records for bulk insert [jobs] job_name=Jira
2025-09-04T01:19:52.243526Z [info] [JIRA] Starting optimized Jira sync (ID: 123) [app.jobs.jira.jira_job]
```

## 🚀 Features

### **📊 Table-Based Log Viewer**
- **Structured Display**: Logs displayed in a clean table format with columns for Time, Level, Module, and Message
- **Real-time Updates**: Live log streaming with automatic refresh
- **Level Filtering**: Filter logs by severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Search Functionality**: Full-text search across all log entries
- **Pagination**: Efficient handling of large log files with pagination controls

### **🗂️ File Management**
- **File List**: View all available log files with metadata (size, modification date)
- **Download**: Download individual log files or bulk download as ZIP
- **Delete/Clear**: Remove old log files or clear current logs
- **Bulk Operations**: Mass delete operations with age-based filtering

### **🎨 Modern Interface**
- **Dark Theme**: Professional dark theme optimized for log viewing
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile
- **Color-Coded Levels**: Visual distinction between log levels
- **Loading States**: Smooth loading indicators and transitions

## 📍 Access Points

### **Web Interface**
```
Primary: http://localhost:8000/logs
Direct:  http://localhost:8000/api/v1/logs/viewer
```

### **API Endpoints**
```
GET  /api/v1/logs/files     - List available log files
GET  /api/v1/logs/content   - Get log content with filtering
POST /api/v1/logs/download  - Download logs as ZIP
POST /api/v1/logs/delete    - Delete specific log files
POST /api/v1/logs/clear     - Clear current log file
```

## 🔧 Usage Guide

### **Viewing Logs**
1. Navigate to the logs interface at `/logs`
2. Select log level filter from dropdown (All, DEBUG, INFO, WARNING, ERROR, CRITICAL)
3. Use search box to find specific entries
4. Navigate through pages using pagination controls
5. Click on entries to view full details

### **Filtering Options**
- **Level Filter**: Show only logs of specific severity
- **Search Filter**: Text search across all log fields
- **Date Range**: Filter logs by time period (if implemented)
- **Module Filter**: Filter by specific application modules

### **Real-time Monitoring**
- **Auto-refresh**: Logs update automatically every 5 seconds
- **Live Streaming**: New entries appear without page reload
- **Pause/Resume**: Control auto-refresh behavior
- **Scroll Lock**: Maintain scroll position during updates

## 📁 File Management

### **File Operations**
1. **View Files**: See all log files in the file list section
2. **Download Single**: Click download button (📥) next to any file
3. **Bulk Download**: Use "Download All" button for ZIP archive
4. **Delete Files**: Use delete button (🗑️) for individual files
5. **Clear Current**: Use "Clear Current Log" to empty active log file

### **Bulk Cleanup**
1. **Age-based Deletion**: Select time threshold (7, 14, 30, 60, 90 days)
2. **Size-based Cleanup**: Remove files exceeding size limits
3. **Confirmation Dialogs**: Safety prompts before destructive operations
4. **Progress Feedback**: Real-time feedback on cleanup operations

## 🎛️ Configuration

### **Environment Variables**
```bash
# Log file location (auto-detected)
LOG_DIR=logs/
LOG_FILE=logs/etl_service.log

# Log level for filtering
LOG_LEVEL=INFO

# Auto-refresh interval (seconds)
LOG_REFRESH_INTERVAL=5

# Maximum log file size (MB)
MAX_LOG_FILE_SIZE=100

# Log retention period (days)
LOG_RETENTION_DAYS=30
```

### **Structured Logging Configuration**
```python
# Structured logging with structlog
import structlog
from structlog.processors import TimeStamper, StackInfoRenderer
from structlog.dev import ColoredConsoleRenderer

# Configure structlog for colorful output
shared_processors = [
    structlog.stdlib.filter_by_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    TimeStamper(fmt="ISO"),
    StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

# Use colored console renderer for development
processors = shared_processors + [ColoredConsoleRenderer()]

structlog.configure(
    processors=processors,
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    context_class=dict,
    cache_logger_on_first_use=True,
)

# Example usage
logger = structlog.get_logger("app.module")
logger.info("[HTTP] Request processed", method="GET", status_code=200, response_time_ms=45.2)
```

## 🔍 Troubleshooting

### **Common Issues**

#### **Logs Not Loading**
- Check if log file exists in the logs directory
- Verify file permissions (read access required)
- Ensure LOG_DIR environment variable is correct
- Check for disk space issues

#### **Performance Issues**
- Large log files may load slowly - consider log rotation
- Increase pagination size for better performance
- Use filtering to reduce data load
- Clear old logs regularly

#### **Search Not Working**
- Verify search terms are correctly formatted
- Check if logs contain the expected content
- Try broader search terms
- Clear browser cache if issues persist

### **Debug Information**
Use the debug endpoints for troubleshooting:
```http
GET /api/v1/debug/system
GET /api/v1/debug/connections
```

## 📚 Related Documentation

- [ETL Service README](../README.md) - Main service documentation
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [System Architecture](../../../docs/architecture.md) - Overall system design

---

**🚀 Built for efficient log management and operational excellence**
