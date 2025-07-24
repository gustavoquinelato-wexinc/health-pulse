# Frontend Architecture

## Overview

The Pulse Frontend follows a modern React architecture with clear separation of concerns, type safety, and performance optimization.

## Architecture Principles

### 1. Component-Based Architecture
- **Atomic Design**: Components are organized from atoms (Button, Input) to organisms (HomePage)
- **Composition over Inheritance**: Use composition patterns for flexibility
- **Single Responsibility**: Each component has a single, well-defined purpose

### 2. State Management
- **Context API**: Used for global state (authentication, theme)
- **Local State**: Component-level state with useState and useReducer
- **Server State**: Managed through API client with caching

### 3. Type Safety
- **TypeScript**: Full type coverage across the application
- **Runtime Validation**: Zod schemas for API responses and form validation
- **Strict Mode**: TypeScript strict mode enabled

## Directory Structure

```
src/
├── components/          # Reusable UI components
│   ├── ui/             # Base design system components
│   │   ├── Button.tsx  # Button component with variants
│   │   ├── Card.tsx    # Card layout component
│   │   ├── Input.tsx   # Form input component
│   │   └── Badge.tsx   # Status badge component
│   └── ProtectedRoute.tsx # Route protection wrapper
├── contexts/           # React contexts for global state
│   └── AuthContext.tsx # Authentication state management
├── lib/               # Utility libraries and configurations
│   ├── api.ts         # API client with interceptors
│   └── utils.ts       # Helper functions and utilities
├── pages/             # Page-level components
│   ├── HomePage.tsx   # Dashboard homepage
│   └── LoginPage.tsx  # Authentication page
├── types/             # TypeScript type definitions
│   ├── auth.ts        # Authentication-related types
│   └── api.ts         # API response types
├── App.tsx            # Root application component
├── main.tsx           # Application entry point
└── index.css          # Global styles and design tokens
```

## Component Architecture

### Base Components (UI Layer)
Located in `src/components/ui/`, these are the foundational building blocks:

- **Button**: Polymorphic button with size and variant props
- **Card**: Layout component for content containers
- **Input**: Form input with validation states
- **Badge**: Status indicators with semantic colors

### Page Components
Located in `src/pages/`, these represent full application screens:

- **LoginPage**: Authentication interface with form validation
- **HomePage**: Dashboard with metrics and quick actions

### Context Providers
Located in `src/contexts/`, these manage global application state:

- **AuthContext**: User authentication, token management, and session handling

## State Management Strategy

### Authentication State
```typescript
interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<void>
}
```

### API State Management
- **Centralized Client**: Single API client with request/response interceptors
- **Error Handling**: Global error handling with user-friendly messages
- **Token Management**: Automatic token attachment and refresh

## Design System Integration

### CSS Custom Properties
The application uses CSS custom properties for theming:

```css
:root {
  --primary: 221.2 83.2% 53.3%;
  --secondary: 210 40% 96%;
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
}
```

### Component Variants
Using `class-variance-authority` for type-safe component variants:

```typescript
const buttonVariants = cva(
  "inline-flex items-center justify-center...",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        outline: "border border-input bg-background",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 px-3",
        lg: "h-11 px-8",
      },
    },
  }
)
```

## Performance Optimizations

### Code Splitting
- **Route-based**: Automatic code splitting at route level
- **Component-based**: Lazy loading for heavy components
- **Vendor Chunks**: Separate chunks for third-party libraries

### Bundle Optimization
```typescript
// vite.config.ts
rollupOptions: {
  output: {
    manualChunks: {
      vendor: ['react', 'react-dom'],
      router: ['react-router-dom'],
      ui: ['framer-motion', 'lucide-react'],
    },
  },
}
```

### Image Optimization
- **Lazy Loading**: Images load as they enter viewport
- **Responsive Images**: Multiple sizes for different screen densities
- **Format Optimization**: WebP with fallbacks

## Security Considerations

### Authentication Security
- **JWT Tokens**: Secure token-based authentication
- **HTTP-Only Cookies**: Fallback storage for enhanced security
- **Token Expiration**: Automatic token refresh and validation
- **Route Protection**: Authentication guards on protected routes

### XSS Prevention
- **Content Security Policy**: Strict CSP headers
- **Input Sanitization**: All user inputs are sanitized
- **Safe HTML Rendering**: React's built-in XSS protection

### API Security
- **HTTPS Only**: All API communication over HTTPS in production
- **Request Validation**: Client-side validation with server-side verification
- **Error Handling**: No sensitive information in error messages

## Testing Strategy

### Unit Testing
- **Component Testing**: React Testing Library for component behavior
- **Utility Testing**: Jest for utility functions
- **Hook Testing**: Custom hooks testing with React Hooks Testing Library

### Integration Testing
- **API Integration**: Mock API responses for consistent testing
- **Authentication Flow**: End-to-end authentication testing
- **Route Testing**: Navigation and route protection testing

### Accessibility Testing
- **Screen Reader**: Testing with screen reader software
- **Keyboard Navigation**: Full keyboard accessibility
- **Color Contrast**: WCAG 2.1 AA compliance

## Development Workflow

### Local Development
1. Start ETL service on port 8000
2. Run `npm run dev` for frontend development server
3. Use browser dev tools for debugging
4. Hot reload for instant feedback

### Build Process
1. TypeScript compilation with type checking
2. Tailwind CSS processing and purging
3. Vite bundling with optimization
4. Asset optimization and compression

### Deployment
1. Environment-specific configuration
2. Production build with optimizations
3. Static asset serving with CDN
4. Health checks and monitoring
