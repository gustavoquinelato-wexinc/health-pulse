# Design System

## Overview

The Pulse Frontend implements a modern, accessible design system built on Tailwind CSS with custom design tokens and components.

## Design Principles

### 1. Clean Minimalism
- **Crisp Borders**: Clean lines instead of heavy blur effects
- **Subtle Shadows**: Minimal shadow usage for depth
- **White Space**: Generous spacing for breathing room
- **Typography Hierarchy**: Clear information hierarchy

### 2. Professional Aesthetics
- **Enterprise-Ready**: Suitable for business environments
- **Consistent Branding**: WEX Health brand integration
- **Trustworthy Colors**: Professional color palette
- **Accessible Design**: WCAG 2.1 AA compliance

### 3. Performance-First
- **Optimized Assets**: Compressed images and fonts
- **Minimal CSS**: Utility-first approach with purging
- **Fast Animations**: 60fps smooth animations
- **Efficient Rendering**: Optimized component rendering

## Color System

### Primary Palette
```css
/* Blue - Primary */
--primary: 221.2 83.2% 53.3%;        /* #3b82f6 */
--primary-foreground: 210 40% 98%;   /* #f8fafc */

/* Violet - Secondary */
--secondary: 210 40% 96%;             /* #f1f5f9 */
--secondary-foreground: 222.2 84% 4.9%; /* #0f172a */

/* Emerald - Accent */
--accent: 210 40% 96%;                /* #f1f5f9 */
--accent-foreground: 222.2 84% 4.9%; /* #0f172a */
```

### Semantic Colors
```css
/* Success */
--success: 142.1 76.2% 36.3%;        /* #16a34a */

/* Warning */
--warning: 32.9 94.6% 43.7%;         /* #d97706 */

/* Error */
--destructive: 0 84.2% 60.2%;        /* #ef4444 */

/* Info */
--info: 204.4 94% 53.9%;             /* #3b82f6 */
```

### Neutral Palette
```css
/* Background */
--background: 0 0% 100%;              /* #ffffff */
--foreground: 222.2 84% 4.9%;        /* #0f172a */

/* Muted */
--muted: 210 40% 96%;                 /* #f1f5f9 */
--muted-foreground: 215.4 16.3% 46.9%; /* #64748b */

/* Border */
--border: 214.3 31.8% 91.4%;         /* #e2e8f0 */
--input: 214.3 31.8% 91.4%;          /* #e2e8f0 */
```

## Typography

### Font Family
```css
font-family: 'Inter', system-ui, sans-serif;
```

### Type Scale
```css
/* Headings */
.text-4xl { font-size: 2.25rem; line-height: 2.5rem; }    /* 36px */
.text-3xl { font-size: 1.875rem; line-height: 2.25rem; }  /* 30px */
.text-2xl { font-size: 1.5rem; line-height: 2rem; }       /* 24px */
.text-xl  { font-size: 1.25rem; line-height: 1.75rem; }   /* 20px */
.text-lg  { font-size: 1.125rem; line-height: 1.75rem; }  /* 18px */

/* Body */
.text-base { font-size: 1rem; line-height: 1.5rem; }      /* 16px */
.text-sm   { font-size: 0.875rem; line-height: 1.25rem; } /* 14px */
.text-xs   { font-size: 0.75rem; line-height: 1rem; }     /* 12px */
```

### Font Weights
```css
.font-light     { font-weight: 300; }
.font-normal    { font-weight: 400; }
.font-medium    { font-weight: 500; }
.font-semibold  { font-weight: 600; }
.font-bold      { font-weight: 700; }
```

## Spacing System

### Scale
```css
/* 4px base unit */
.space-1  { margin: 0.25rem; }   /* 4px */
.space-2  { margin: 0.5rem; }    /* 8px */
.space-3  { margin: 0.75rem; }   /* 12px */
.space-4  { margin: 1rem; }      /* 16px */
.space-6  { margin: 1.5rem; }    /* 24px */
.space-8  { margin: 2rem; }      /* 32px */
.space-12 { margin: 3rem; }      /* 48px */
.space-16 { margin: 4rem; }      /* 64px */
```

## Component Specifications

### Button
```typescript
interface ButtonProps {
  variant: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size: 'default' | 'sm' | 'lg' | 'icon'
}
```

**Variants:**
- `default`: Primary blue background
- `outline`: Transparent with border
- `secondary`: Light gray background
- `ghost`: Transparent with hover state
- `destructive`: Red for dangerous actions

**Sizes:**
- `sm`: 36px height, compact padding
- `default`: 40px height, standard padding
- `lg`: 44px height, generous padding
- `icon`: 40x40px square for icons

### Card
```typescript
interface CardProps {
  className?: string
  children: ReactNode
}
```

**Structure:**
- `Card`: Container with border and shadow
- `CardHeader`: Top section with padding
- `CardTitle`: Heading element
- `CardDescription`: Subtitle text
- `CardContent`: Main content area
- `CardFooter`: Bottom section for actions

### Input
```typescript
interface InputProps extends HTMLInputAttributes {
  error?: boolean
  helperText?: string
}
```

**States:**
- `default`: Normal state with border
- `focus`: Blue ring and border
- `error`: Red border and ring
- `disabled`: Reduced opacity

## Layout System

### Grid
```css
/* 12-column grid */
.grid-cols-1   { grid-template-columns: repeat(1, minmax(0, 1fr)); }
.grid-cols-2   { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-cols-3   { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-cols-4   { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.grid-cols-6   { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.grid-cols-12  { grid-template-columns: repeat(12, minmax(0, 1fr)); }
```

### Flexbox
```css
.flex           { display: flex; }
.flex-col       { flex-direction: column; }
.items-center   { align-items: center; }
.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
```

### Container
```css
.container {
  width: 100%;
  margin-left: auto;
  margin-right: auto;
  padding-left: 1rem;
  padding-right: 1rem;
}

/* Responsive breakpoints */
@media (min-width: 640px) {
  .container { max-width: 640px; }
}
@media (min-width: 768px) {
  .container { max-width: 768px; }
}
@media (min-width: 1024px) {
  .container { max-width: 1024px; }
}
@media (min-width: 1280px) {
  .container { max-width: 1280px; }
}
```

## Responsive Design

### Breakpoints
```css
/* Mobile first approach */
sm:   640px   /* Small devices */
md:   768px   /* Medium devices */
lg:   1024px  /* Large devices */
xl:   1280px  /* Extra large devices */
2xl:  1536px  /* 2X large devices */
3xl:  1920px  /* Ultra wide */
4xl:  2560px  /* 4K displays */
```

### Usage
```jsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  {/* Responsive grid */}
</div>
```

## Animation System

### Transitions
```css
.transition-colors { transition: color 0.2s ease, background-color 0.2s ease; }
.transition-all    { transition: all 0.2s ease; }
.transition-transform { transition: transform 0.2s ease; }
```

### Animations
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes scaleIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
```

## Accessibility

### Focus States
```css
.focus-visible:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 2px;
}
```

### Color Contrast
- **AA Compliance**: Minimum 4.5:1 contrast ratio
- **AAA Preferred**: 7:1 contrast ratio for important text
- **Testing**: Regular contrast testing with tools

### Keyboard Navigation
- **Tab Order**: Logical tab sequence
- **Focus Indicators**: Visible focus states
- **Skip Links**: Navigation shortcuts
- **ARIA Labels**: Proper labeling for screen readers

## Dark Mode

### Implementation
```css
.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --card: 222.2 84% 4.9%;
  --card-foreground: 210 40% 98%;
  /* ... other dark mode variables */
}
```

### Usage
```jsx
<div className="bg-background text-foreground">
  {/* Automatically adapts to dark mode */}
</div>
```

## Best Practices

### Component Development
1. **Use semantic HTML**: Proper HTML elements for accessibility
2. **Implement focus states**: Visible focus indicators
3. **Add loading states**: Skeleton loaders and spinners
4. **Handle errors gracefully**: User-friendly error messages
5. **Test responsiveness**: Multiple screen sizes

### Performance
1. **Optimize images**: WebP format with fallbacks
2. **Minimize CSS**: Use Tailwind's purge feature
3. **Lazy load components**: Code splitting for large components
4. **Efficient animations**: Use transform and opacity
5. **Monitor bundle size**: Regular bundle analysis
