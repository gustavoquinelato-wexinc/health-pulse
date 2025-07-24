# Pulse Platform - Authentication Instructions

## 🚀 Quick Start

The application is now configured with **real authentication** connected to the backend service.

### Login Credentials
You need to use **valid user credentials** that exist in the database. The system will authenticate against the backend service.

**To create a user account:**
1. Make sure the backend service is running on port 3001
2. Use the admin interface or API to create user accounts
3. Or check with your administrator for existing credentials

### What Happens During Login
1. The system makes a real API call to `/auth/login` on the backend service
2. Backend validates credentials against the database
3. Creates a JWT session token and stores it in the database
4. Returns user information and token to the frontend
5. Frontend stores the token and redirects to the main dashboard

### Testing Different Experiences

Once logged in, you can test different navigation experiences:

1. **Default Experience (Option A)**: `/home`
   - Collapsed sidebar with header integration
   - Quick Actions and Recent items in header dropdowns

2. **Alternative Experience (Option B)**: `/home-option-b`
   - Expandable sidebar with pin functionality
   - Recent and Quick Actions integrated in sidebar when expanded

3. **Original Backup**: `/home-backup`
   - Original design for comparison

### Navigation Structure
- 🏠 **Home** - Welcome page
- 📊 **DORA Metrics** - DevOps metrics with hover submenu:
  - Overview (click main icon)
  - Deployment Frequency (hover submenu)
  - Lead Time for Changes (hover submenu)
  - Time to Restore Service (hover submenu)
  - Change Failure Rate (hover submenu)
- ⚙️ **Engineering Analytics** - Comprehensive engineering metrics
- 🔧 **Settings** - Color schema customization

### Features to Test
- **Color Schema Customization** - Available in Settings page
- **Theme Toggle** - Light/Dark mode in header
- **Responsive Design** - Test on different screen sizes
- **Navigation** - Hover effects and submenu interactions
  - **DORA Submenu** - Hover over 📊 icon to see 4 metric options
  - **Smooth Transitions** - 200ms grace period for mouse movement
  - **Fast Response** - onMouseDown events for immediate navigation
- **Quick Actions** - ETL job and report generation buttons
- **Recent Items** - Activity tracking dropdown

### Notes
- Login page maintains static styling (doesn't change with themes)
- All internal pages follow the 5-color schema system
- WEX branding is prominently displayed
- Professional animations and micro-interactions included

## 🎯 Ready for Production!

The application is now fully functional with real authentication. The frontend connects to the backend service for:

- **User Authentication** - Real login/logout with JWT tokens
- **Session Management** - Database-stored sessions with proper expiration
- **Token Validation** - Automatic token verification on app startup
- **Secure Logout** - Server-side session invalidation

### Prerequisites
- Backend service must be running on port 3001
- Database must be accessible and contain user accounts
- Valid user credentials are required for login

### Session Separation
- Frontend sessions (via backend-service) are independent from ETL service sessions
- Users can be logged into both systems simultaneously
- Each service maintains its own session management
