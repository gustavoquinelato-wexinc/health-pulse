# Log Management System

## 🎯 Overview

The ETL Service includes a comprehensive log management system with a modern web interface for viewing, managing, and maintaining log files.

## 🚀 Features

### **📊 Table-Based Log Viewer**
- **Structured Display**: Logs displayed in a clean table format with columns for Time, Level, Module, and Message
- **Pagination**: Navigate through logs with 20 entries per page
- **Auto-refresh**: Logs automatically load when opening the management modal
- **Color-coded Levels**: Visual distinction for ERROR (red), WARNING (yellow), INFO (blue), and DEBUG (gray)
- **Smart Parsing**: Automatically extracts timestamp, level, module, and message from log entries

### **📁 File Management**
- **File Listing**: View all log files with metadata (size, modification date)
- **Individual Actions**: Download or delete/clear specific log files
- **Active Log Handling**: Active log files are cleared (not deleted) to maintain logging functionality
- **Visual Indicators**: Active log files are clearly marked with a green "Active" badge

### **🗑️ Bulk Operations**
- **Age-based Cleanup**: Delete files older than 7, 14, 30, 60, or 90 days
- **Delete All**: Option to delete all log files (clears active log content)
- **Smart Confirmations**: Different confirmation messages for different operations
- **Detailed Feedback**: Shows number of files deleted and space freed

## 🎨 User Interface

### **Modal Layout**
1. **Header**: Title and close button
2. **Current Log Files**: File list with individual actions
3. **Recent Log Entries**: Table view with pagination
4. **Bulk Actions**: Age-based cleanup controls

### **Consistent Dark Theme**
- All modals use consistent dark gray backgrounds (`bg-gray-800`)
- Proper contrast with white text and gray borders
- Professional appearance matching the dashboard design

## 🔧 API Endpoints

### **Log Viewing**
```http
GET /api/v1/logs/recent?lines=100
```
- Returns recent log entries with pagination support
- Supports filtering by level and search terms

### **File Management**
```http
GET /api/v1/logs/files
```
- Lists all available log files with metadata

```http
GET /api/v1/logs/download/{filename}?clean=true&compress=true
```
- Downloads log files as clean ZIP archives (ANSI codes removed)

### **File Operations**
```http
DELETE /api/v1/logs/file/{filename}
```
- Deletes individual log files
- Clears content for active log files instead of deleting

```http
DELETE /api/v1/logs/cleanup?days=30
```
- Bulk delete files older than specified days
- Use `days=0` for "delete all" operation

## 🛡️ Safety Features

### **Active Log Protection**
- Active log files cannot be deleted
- Instead, their content is cleared while maintaining the file
- Clear visual indication with green "Active" badge
- Different icons: eraser (🧹) for active logs, trash (🗑️) for old logs

### **Confirmation Dialogs**
- **Individual Delete**: "Are you sure you want to delete 'filename'?"
- **Active Log Clear**: "Are you sure you want to clear all content from 'filename'? This will empty the active log file."
- **Bulk Delete**: "Are you sure you want to delete ALL log files older than X days?"
- **Delete All**: Multi-line confirmation explaining the operation

### **Error Handling**
- Graceful handling of file access errors
- Clear error messages for failed operations
- Automatic refresh after successful operations

## 📈 Performance Features

### **Efficient Processing**
- **Pagination**: Only loads 20 entries at a time
- **Smart Parsing**: Efficient regex-based log entry parsing
- **Bulk Operations**: Efficient file system operations
- **Auto-refresh**: Updates file list and log table after operations

### **User Experience**
- **Instant Feedback**: Immediate UI updates after operations
- **Loading States**: Clear loading indicators during operations
- **Responsive Design**: Works well on different screen sizes
- **Keyboard Navigation**: Proper tab order and accessibility

## 🔍 Log Format Support

### **Supported Format**
```
2025-07-21 14:08:48 - app.api.web_routes - INFO - Message content
```

### **Parsed Components**
- **Timestamp**: `2025-07-21 14:08:48`
- **Module**: `app.api.web_routes`
- **Level**: `INFO`
- **Message**: Clean message content (redundant info removed)

### **Message Cleaning**
The system automatically removes redundant information from messages:
- Duplicate timestamps
- Redundant level indicators (`[info]`, `[error]`)
- Duplicate module references
- Structured logging artifacts

## 🚀 Usage Examples

### **Viewing Recent Logs**
1. Click the "Logs" button in the dashboard header
2. Recent logs automatically load in table format
3. Use pagination controls to navigate through entries
4. Click refresh button to update log entries

### **Managing Log Files**
1. View all log files in the file list section
2. Click download button (📥) to download as ZIP
3. Click delete/clear button (🗑️/🧹) to remove or clear files
4. Use bulk delete controls for maintenance

### **Bulk Cleanup**
1. Select age threshold from dropdown (7-90 days or "All")
2. Click "Delete Old" or "Delete All" button
3. Confirm the operation in the dialog
4. View feedback showing files deleted and space freed

## 🔧 Configuration

### **Environment Variables**
```bash
# Log file location (auto-detected)
LOG_DIR=logs/
LOG_FILE=logs/etl_service.log

# Log level for filtering
LOG_LEVEL=INFO
```

### **Pagination Settings**
- **Logs per page**: 20 entries (configurable in JavaScript)
- **Max log lines**: 200 lines fetched from API (10 pages worth)
- **Auto-refresh**: Enabled by default

## 🐛 Troubleshooting

### **Common Issues**

#### **Logs Not Loading**
- Check if log file exists and is readable
- Verify file permissions
- Check for encoding issues (system handles UTF-8 and latin-1)

#### **File Operations Failing**
- Ensure sufficient disk space
- Check file permissions
- Verify no other processes are locking files

#### **UI Not Updating**
- Check browser console for JavaScript errors
- Verify WebSocket connections are working
- Try refreshing the page

### **Debug Information**
Use the debug endpoints for troubleshooting:
```http
GET /api/v1/debug/system
GET /api/v1/debug/connections
```

## 📚 Related Documentation

- [ETL Service README](../README.md) - Main service documentation
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [System Architecture](../../../docs/architecture/overview.md) - Overall system design

---

**🚀 Built for efficient log management and operational excellence**
