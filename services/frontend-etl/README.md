# ETL Frontend - New ETL Architecture

**Modern React + TypeScript frontend for Pulse Platform ETL Management**

## 🎯 Overview

This is the **NEW** ETL frontend that replaces the legacy monolithic ETL service (`services/etl-service/`). Built with modern web technologies for better performance, maintainability, and user experience.

**⚠️ IMPORTANT**:
- **Old ETL Service**: `services/etl-service/` - **DO NOT MODIFY** (legacy backup/reference only)
- **New ETL Frontend**: `services/etl-frontend/` - **CURRENT** (this service)
- **New ETL Backend**: `services/backend-service/app/etl/` - **CURRENT**
- **Migration Guide**: See `docs/ETL.md` for complete architecture details

## ✨ Key Features

- ✅ **Modern Stack**: React 18 + TypeScript + Vite
- ✅ **Responsive Design**: Mobile-friendly with Tailwind CSS
- ✅ **Dark Mode**: Full theme support with auto-inverting logos
- ✅ **Real-time Updates**: Job status and progress monitoring
- ✅ **Type Safety**: Full TypeScript coverage
- ✅ **Fast Development**: Hot module replacement with Vite
- ✅ **Job Names**: Always displayed in **UPPERCASE**
- ✅ **Subtle Shadows**: 0.03 opacity in dark mode (vs 0.1 in light)

## 🛠️ Technology Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Framer Motion** for animations
- **Lucide React** for icons
- **React Router** for navigation
- **Axios** for API communication

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm
- Backend service running on port 3001

### Installation

```bash
cd services/frontend-etl
npm install
```

### Development

```bash
npm run dev
# Opens on http://localhost:3333
```

### Build

```bash
npm run build
# Output in dist/
```

### Type Check

```bash
npm run type-check
```

### Environment Variables

Create a `.env` file in the root directory:

```env
VITE_API_BASE_URL=http://localhost:3001
```

## 📁 Project Structure

```
services/frontend-etl/
├── src/
│   ├── components/          # React components
│   │   ├── Header.tsx       # App header with tenant logo
│   │   ├── CollapsedSidebar.tsx  # Navigation sidebar
│   │   ├── JobCard.tsx      # Job display card (UPPERCASE names)
│   │   ├── IntegrationLogo.tsx   # Auto-inverting logo component
│   │   ├── *Modal.tsx       # Various modal dialogs
│   │   └── ...
│   ├── pages/               # Page components
│   │   ├── HomePage.tsx     # Job management dashboard
│   │   ├── WitsPage.tsx     # Work item types
│   │   ├── StatusesPage.tsx # Status management
│   │   ├── HierarchiesPage.tsx  # Hierarchy levels
│   │   ├── WorkflowsPage.tsx    # Workflow management
│   │   ├── IntegrationsPage.tsx # Integration providers
│   │   └── QdrantPage.tsx   # Vector database
│   ├── contexts/            # React contexts
│   │   ├── AuthContext.tsx  # Authentication state
│   │   └── ThemeContext.tsx # Theme (dark/light) state
│   ├── hooks/               # Custom React hooks
│   │   ├── useToast.ts      # Toast notifications
│   │   └── useLogoFilter.ts # Logo color inversion
│   ├── utils/               # Utility functions
│   │   └── imageColorUtils.ts  # Image color analysis
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles (Tailwind)
├── public/
│   └── assets/
│       └── integrations/    # Integration logo files
├── .vscode/                 # VSCode settings
│   ├── settings.json        # Workspace settings (Tailwind warnings suppressed)
│   └── extensions.json      # Recommended extensions
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Key Features

### Authentication
- Secure login with JWT tokens
- Protected routes and admin-only sections
- Cross-service authentication with main analytics app

### ETL Management
- Job status monitoring and control
- Performance analytics and metrics
- Data quality monitoring
- Vectorization queue management

### UI/UX
- Consistent design system with the main analytics app
- Responsive sidebar navigation
- Real-time status updates
- Smooth animations and transitions

## API Integration

The frontend communicates with:
- **Backend Service** (port 3001): Authentication, core APIs, and ETL operations
- **Analytics App** (port 3000): Cross-navigation and shared resources

## Deployment

The application builds to static files that can be served by any web server:

```bash
npm run build
# Files will be in the 'dist' directory
```

## 🎨 Design System

### Color Scheme
Uses CSS variables for theming:
- `--color-1` through `--color-5`: Primary colors
- `--gradient-1-2`: Diagonal gradient
- `--on-gradient-1-2`: Text color on gradient
- `--bg-primary`, `--bg-secondary`, `--bg-tertiary`: Background colors
- `--text-primary`, `--text-secondary`: Text colors

### Dark Mode
- Automatic theme detection
- Manual toggle in header
- **Subtle shadows**: 0.03 opacity (vs 0.1 in light mode)
- **Auto-inverting logos**: Dark logos become white automatically

### Typography
- **Job Names**: Always displayed in **UPPERCASE** (`.toUpperCase()`)
- **Font**: System font stack for performance
- **Sizes**: Responsive with Tailwind classes

## 🧩 Key Components

### JobCard
Displays job information with status, controls, and countdown timer.
**Note**: Job names are displayed in UPPERCASE.

### IntegrationLogo
Auto-inverting logo component for dark mode support.
Uses luminance detection to automatically invert dark logos to white.

### Toast Notifications
```tsx
const { showSuccess, showError, showWarning, showInfo } = useToast()

showSuccess('Success!', 'Job started successfully')
showError('Error', 'Failed to start job')
```

## 🐛 Debugging

### VSCode Settings
The project includes VSCode settings that:
- ✅ Suppress Tailwind CSS warnings (`@tailwind`, `@apply`)
- ✅ Enable TypeScript workspace mode
- ✅ Configure Prettier formatting
- ✅ Set up ESLint

### Common Issues

**Issue**: CSS warnings about `@tailwind` and `@apply`
**Solution**: Already suppressed in `.vscode/settings.json`

**Issue**: Logo not inverting in dark mode
**Solution**: Check `useLogoFilter` hook and `imageColorUtils.ts`

**Issue**: Job names not uppercase
**Solution**: Use `.toUpperCase()` on all job name displays

**Issue**: Shadows too bright in dark mode
**Solution**: Use 0.03 opacity for dark mode shadows

## 📚 Related Documentation

- **⚠️ ETL Architecture**: `docs/ETL.md` (READ THIS FIRST!)
- **System Architecture**: `docs/ARCHITECTURE_NEW.md`
- **Security**: `docs/SECURITY.md`
- **Installation**: `docs/INSTALLATION.md`
- **Old ETL Service**: `services/etl-service/README.md` (LEGACY - reference only)

## 🚫 What NOT to Do

- ❌ Don't modify the old ETL service (`services/etl-service/`)
- ❌ Don't use inline styles (use Tailwind classes)
- ❌ Don't hardcode colors (use CSS variables)
- ❌ Don't forget to test dark mode
- ❌ Don't use `any` type in TypeScript
- ❌ Don't display job names in lowercase (always UPPERCASE)
- ❌ Don't add console.log statements (removed from production)

## ✅ What TO Do

- ✅ **Check old ETL service** (`services/etl-service/`) for business logic reference
- ✅ Use TypeScript for type safety
- ✅ Use Tailwind CSS for styling
- ✅ Test in both light and dark modes
- ✅ Follow existing component patterns
- ✅ Update documentation when adding features
- ✅ Display job names in UPPERCASE
- ✅ Use `IntegrationLogo` component for logos (auto-inversion)
- ✅ Keep shadows subtle in dark mode (0.03 opacity)

## 📞 Support

For questions or issues:
- **Migration Guide**: `docs/etl/NEW_ETL_ARCHITECTURE.md`
- Review existing components for patterns
- Contact the development team

---

**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Status**: Active Development
**Port**: 3333 (development)
