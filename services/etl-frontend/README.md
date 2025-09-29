# ETL Frontend

A React-based frontend application for managing ETL (Extract, Transform, Load) operations and data pipelines.

## Features

- **ETL Job Management**: Monitor and control data pipeline jobs
- **Analytics Dashboard**: Performance metrics and data quality insights  
- **Vectorization Management**: AI embedding and vector processing
- **Real-time Monitoring**: Live status updates and notifications
- **Theme Support**: Light/dark mode with custom color schemes
- **Responsive Design**: Works on desktop and mobile devices

## Technology Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Framer Motion** for animations
- **Lucide React** for icons
- **React Router** for navigation
- **Axios** for API communication

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server (runs on port 3333)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Environment Variables

Create a `.env` file in the root directory:

```env
VITE_API_BASE_URL=http://localhost:3001
VITE_ETL_SERVICE_URL=http://localhost:8000
```

## Project Structure

```
src/
├── components/          # Reusable UI components
├── contexts/           # React contexts (Auth, Theme)
├── pages/              # Page components
├── types/              # TypeScript type definitions
├── utils/              # Utility functions
├── App.tsx             # Main app component
├── main.tsx            # App entry point
└── index.css           # Global styles
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
- **Backend Service** (port 3001): Authentication and core APIs
- **ETL Service** (port 8000): ETL-specific operations
- **Analytics App** (port 3000): Cross-navigation and shared resources

## Deployment

The application builds to static files that can be served by any web server:

```bash
npm run build
# Files will be in the 'dist' directory
```

## Development Notes

- Uses the same authentication system as the main analytics app
- Shares color schemes and theming with the main app
- Designed to work alongside the existing ETL service
- Port 3333 is used to avoid conflicts with other services
