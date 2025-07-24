# Admin Page Template and Guidelines

## 📋 **Overview**

This document provides a template and guidelines for creating new admin pages that are consistent with the existing admin interface design and functionality.

## 🎯 **Critical Authentication Pattern**

### **❌ Common Mistake**
```javascript
// WRONG - Only checks localStorage
function getAuthToken() {
    const token = localStorage.getItem('authToken');  // ❌ Wrong key and missing cookie check
    if (!token) {
        alert('Authentication required. Please log in.');
        window.location.href = '/login';
        return null;
    }
    return token;
}
```

### **✅ Correct Pattern**
```javascript
// CORRECT - Checks both localStorage and cookies
function getAuthToken() {
    // Try localStorage first (for compatibility)
    let token = localStorage.getItem('pulse_token') || localStorage.getItem('token');

    // If not in localStorage, try to get from cookie
    if (!token) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'pulse_token' || name === 'access_token') {
                token = value;
                break;
            }
        }
    }

    return token;
}
```

## 🎨 **Page Structure Template**

### **1. HTML Structure**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Feature Management - Pulse ETL</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .admin-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem 0;
            margin-bottom: 2rem;
        }
    </style>
</head>
<body class="bg-light">
    <!-- Navigation (copy from working admin page) -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <!-- ... navigation content ... -->
    </nav>

    <!-- Header -->
    <div class="admin-header">
        <div class="container">
            <div class="row align-items-center">
                <div class="col">
                    <h1 class="mb-0">
                        <i class="fas fa-your-icon me-3"></i>Your Feature Management
                    </h1>
                    <p class="mb-0 mt-2 opacity-75">Manage your feature description</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="container my-5">
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-white border-0 py-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">
                                <i class="fas fa-list me-2"></i>Your Features
                            </h5>
                            <div>
                                <button class="btn btn-outline-secondary btn-sm me-2" onclick="refreshYourFeatures()">
                                    <i class="fas fa-sync-alt"></i> Refresh
                                </button>
                                <button class="btn btn-primary btn-sm" onclick="showCreateModal()">
                                    <i class="fas fa-plus"></i> Add Feature
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="card-body">
                        <!-- Search and Filters -->
                        <div class="row mb-3">
                            <div class="col-md-4">
                                <label for="searchFeature" class="form-label">Search Features</label>
                                <input type="text" class="form-control" id="searchFeature" placeholder="Type to search..." onkeyup="applyFilters()">
                            </div>
                            <div class="col-md-4">
                                <label for="filterActive" class="form-label">Filter Status</label>
                                <select class="form-control" id="filterActive" onchange="applyFilters()">
                                    <option value="">All Statuses</option>
                                    <option value="true">Active</option>
                                    <option value="false">Inactive</option>
                                </select>
                            </div>
                            <div class="col-md-4">
                                <!-- Additional filter as needed -->
                            </div>
                        </div>
                        
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead class="table-light">
                                    <tr>
                                        <th class="sortable" onclick="sortTable('name')">
                                            Name <i class="fas fa-sort" id="sort-name"></i>
                                        </th>
                                        <th class="sortable" onclick="sortTable('description')">
                                            Description <i class="fas fa-sort" id="sort-description"></i>
                                        </th>
                                        <th class="sortable" onclick="sortTable('active')">
                                            Status <i class="fas fa-sort" id="sort-active"></i>
                                        </th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="features-table-body">
                                    <tr>
                                        <td colspan="4" class="text-center text-muted py-4">
                                            <i class="fas fa-spinner fa-spin me-2"></i>Loading features...
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modals and JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // CRITICAL: Use this exact authentication function
        function getAuthToken() {
            let token = localStorage.getItem('pulse_token') || localStorage.getItem('token');
            if (!token) {
                const cookies = document.cookie.split(';');
                for (let cookie of cookies) {
                    const [name, value] = cookie.trim().split('=');
                    if (name === 'pulse_token' || name === 'access_token') {
                        token = value;
                        break;
                    }
                }
            }
            return token;
        }

        // Your JavaScript functions here...
    </script>
</body>
</html>
```

## 🔧 **Backend Route Template**

```python
@router.get("/admin/your-feature", response_class=HTMLResponse)
async def your_feature_page(request: Request):
    """Serve your feature management page"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission
        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        database = get_database()
        with database.get_session() as session:
            if not has_permission(user, Resource.ADMIN_PANEL, Action.READ, session):
                return RedirectResponse(url="/login?error=permission_denied&resource=admin_panel", status_code=302)

        return templates.TemplateResponse("admin_your_feature.html", {"request": request, "user": user})

    except Exception as e:
        logger.error(f"Your feature page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)
```

## 📋 **Checklist for New Admin Pages**

### **✅ Before Creating**
- [ ] Copy from existing working admin page (Flow Steps recommended)
- [ ] Read this template and agent guidance document
- [ ] Plan the data structure and API endpoints

### **✅ During Development**
- [ ] Use exact `getAuthToken()` function from template
- [ ] Follow card-based layout structure
- [ ] Add to ALL admin page navigation menus
- [ ] Include Status column with Active/Inactive badges
- [ ] Implement search and filter functionality
- [ ] Add proper loading states and error handling

### **✅ After Creation**
- [ ] Test authentication works correctly
- [ ] Verify navigation appears in all admin pages
- [ ] Test all CRUD operations
- [ ] Verify responsive design
- [ ] Check browser console for errors

## 🚨 **Common Pitfalls to Avoid**

1. **❌ Wrong Authentication**: Using localStorage-only authentication
2. **❌ Missing Navigation**: Forgetting to add to other admin page menus
3. **❌ Inconsistent Styling**: Not following the card-based layout
4. **❌ Missing Status Column**: Not including active/inactive status
5. **❌ Poor Error Handling**: Not handling API failures gracefully

## 🎯 **Success Criteria**

A properly implemented admin page should:
- **✅ Load without authentication errors**
- **✅ Match the visual style of other admin pages**
- **✅ Be accessible from all admin page navigation menus**
- **✅ Handle all CRUD operations correctly**
- **✅ Provide good user feedback and error handling**
