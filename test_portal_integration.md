# Portal Shell Integration - Testing Guide

## 🚀 **Implementation Summary**

We've successfully implemented **Option A: Portal Shell Architecture** with iframe embedding! Here's what was built:

### ✅ **Completed Features**

1. **ServiceFrame Component** (`services/frontend-app/src/components/ServiceFrame.tsx`)
   - Iframe embedding with authentication token passing
   - Real-time theme synchronization via CSS injection
   - PostMessage communication for dynamic updates
   - Loading states and error handling

2. **Portal Navigation** (Updated `CollapsedSidebar.tsx`)
   - Added "ETL Management" section (admin-only)
   - Submenu with: Job Dashboard, Admin Panel, Status Mappings, etc.
   - Proper admin permission filtering

3. **Portal Routes** (`services/frontend-app/src/App.tsx`)
   - `/etl` - ETL dashboard
   - `/etl/:page` - Dynamic ETL pages
   - `/etl/admin/:page` - Admin-specific pages
   - All routes protected with AdminRoute

4. **ETL Management Page** (`services/frontend-app/src/pages/ETLManagementPage.tsx`)
   - Dynamic page configuration
   - Breadcrumb navigation
   - ServiceFrame integration

5. **ETL Service Updates**
   - Updated CSS to use theme variables (`dashboard.css`)
   - Added embedded mode support to templates
   - Token parameter support in routes
   - PostMessage theme listening

6. **Environment Configuration**
   - Added `VITE_ETL_SERVICE_URL` to `.env`
   - Proper service URL configuration

## 🧪 **Testing Steps**

### **Step 1: Start Services**
```bash
# Terminal 1: Backend Service
cd services/backend-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 3002 --reload

# Terminal 2: ETL Service  
cd services/etl-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Frontend Portal
cd services/frontend-app
npm run dev
```

### **Step 2: Test Portal Access**
1. Go to `http://localhost:3000`
2. Login with admin credentials
3. Look for "ETL Management" in sidebar (🔄 icon)
4. Should only appear for admin users

### **Step 3: Test ETL Embedding**
1. Click "ETL Management" → "Job Dashboard"
2. Should load ETL dashboard in iframe
3. Check browser console for:
   - `🔗 ETL Dashboard running in embedded mode`
   - `🎨 Theme injected into ETL iframe`
   - `📨 Theme message sent to ETL iframe`

### **Step 4: Test Theme Synchronization**
1. Go to Settings → Color Scheme
2. Switch between Default/Custom modes
3. Change theme (light/dark)
4. ETL iframe should update colors immediately

### **Step 5: Test Different ETL Pages**
- Job Dashboard: `/etl/dashboard`
- Admin Panel: `/etl/admin`
- Status Mappings: `/etl/admin/status-mappings`
- Issue Type Mappings: `/etl/admin/issuetype-mappings`

## 🎨 **Theme System**

The portal automatically synchronizes:
- **5-Color Schema**: `--color-1` through `--color-5`
- **Theme Mode**: Light/dark mode variables
- **Custom Colors**: Client-specific branding

## 🔧 **Troubleshooting**

### **ETL iframe not loading**
- Check `VITE_ETL_SERVICE_URL` in `.env`
- Verify ETL service is running on port 8000
- Check browser console for CORS errors

### **Theme not synchronizing**
- Check browser console for postMessage errors
- Verify CSS custom properties are defined
- Test with browser dev tools

### **Authentication issues**
- Verify token is being passed in iframe URL
- Check ETL service logs for token validation
- Ensure backend service is running

## 🎯 **Next Steps**

1. **Polish UI**: Add loading animations, better error states
2. **Add More Pages**: Convert remaining ETL admin pages
3. **Performance**: Optimize iframe loading and theme sync
4. **Testing**: Add automated tests for portal integration

## 🏆 **Success Criteria**

✅ **Unified UX**: Single portal experience  
✅ **Theme Consistency**: Colors sync across services  
✅ **Admin Security**: ETL management restricted to admins  
✅ **Service Separation**: ETL and frontend remain independent  
✅ **Multi-Client Ready**: Architecture supports client-specific deployments  

The portal shell is now ready for enterprise use! 🚀
