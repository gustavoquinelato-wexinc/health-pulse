# Pulse Platform Design System

This document defines the comprehensive design system for the Pulse Platform, focusing on color management, accessibility, and user experience consistency across all services.

## Overview

The Pulse Platform Design System provides a unified approach to visual design, color management, and accessibility across Frontend, Backend, and ETL services. It ensures consistent branding, optimal user experience, and WCAG compliance for all clients.

### Key Features

- **🎨 Multi-tenant Color Management**: Client-specific color schemes with default and custom modes
- **♿ Accessibility Compliance**: WCAG AA/AAA support with user-specific preferences
- **⚡ Real-time Updates**: Instant color synchronization across all services
- **🚀 Performance Optimized**: Redis caching and smart color calculations
- **🔧 Developer-Friendly**: CSS variables, TypeScript interfaces, and comprehensive APIs

## Color System Architecture

### Database Schema

The color system uses a modern database architecture with proper relationships:

```sql
-- Main color settings table
client_color_settings (
    id, client_id, color_schema_mode,
    color1..color5,                    -- Base colors
    on_color1..on_color5,             -- Text colors for base colors
    on_gradient_1_2..on_gradient_5_1, -- Text colors for gradients
    adaptive_color1..adaptive_color5   -- Theme-adaptive variants
)

-- Accessibility variants table
client_accessibility_colors (
    id, client_id, color_settings_id,
    accessibility_level,               -- 'AA' or 'AAA'
    contrast_ratio_normal,            -- 4.5 (AA) or 7.0 (AAA)
    [same color columns as main table]
)

-- User preferences table
user_color_preferences (
    user_id, use_accessible_colors,
    theme_mode, accessibility_level
)
```

### Color Modes

**Default Mode**: Professional color palette maintained by the platform team
- Optimized for business use and accessibility
- Automatically updated with platform releases
- Consistent across all clients

**Custom Mode**: Client-specific brand colors
- Fully customizable 5-color palette
- Reflects organization's brand identity
- Persists across platform updates
- Includes automatic accessibility calculations

### Color Palette Structure

The 5-color palette serves specific purposes:

1. **Color 1**: Primary brand color (headers, buttons, primary actions)
2. **Color 2**: Secondary color (navigation, sidebars, secondary elements)
3. **Color 3**: Success/positive actions (confirmations, success states)
4. **Color 4**: Information/neutral actions (info messages, secondary buttons)
5. **Color 5**: Warning/attention (alerts, important notices, highlights)

## Token Model

### Base Colors (Database Stored)
- `color1..color5` - Core brand colors
- `on_color1..on_color5` - Text colors for solid backgrounds
- `on_gradient_1_2..on_gradient_5_1` - Text colors for gradient backgrounds
- `adaptive_color1..adaptive_color5` - Theme-adaptive color variants

### CSS Variables (Runtime Generated)
```css
:root {
  /* Base colors */
  --color-1: #2862EB;
  --color-2: #763DED;
  --color-3: #059669;
  --color-4: #0EA5E9;
  --color-5: #F59E0B;
  
  /* Text colors for solid backgrounds */
  --on-color-1: #FFFFFF;
  --on-color-2: #FFFFFF;
  --on-color-3: #FFFFFF;
  --on-color-4: #000000;
  --on-color-5: #000000;
  
  /* Text colors for gradients */
  --on-gradient-1-2: #FFFFFF;
  --on-gradient-2-3: #FFFFFF;
  --on-gradient-3-4: #000000;
  --on-gradient-4-5: #000000;
  --on-gradient-5-1: #000000;
}
```

## Accessibility System

### WCAG Compliance Levels

**AA Compliance (Standard)**
- Contrast ratio: 4.5:1 for normal text
- Contrast ratio: 3:1 for large text
- Default for all users
- Meets most accessibility requirements

**AAA Compliance (Enhanced)**
- Contrast ratio: 7:1 for normal text
- Contrast ratio: 4.5:1 for large text
- Available as user preference
- Highest accessibility standard

### User Accessibility Preferences

Users can enable enhanced accessibility features:
- **Enhanced Color Contrast**: Switches to AAA-compliant color variants
- **Theme Preference**: Light, dark, or system-based themes
- **Personal Settings**: Individual preferences that don't affect other users

### Automatic Color Calculations

The system automatically calculates:
- **Optimal text colors** using WCAG relative luminance
- **Contrast ratios** meeting specified compliance levels
- **Gradient text colors** optimized for multi-color backgrounds
- **Theme-adaptive colors** for light/dark mode switching

## API Integration

### Admin Color Management

```typescript
// Get current color schema
GET /api/v1/admin/color-schema
Response: {
  mode: 'custom' | 'default',
  colors: { color1: '#FF5733', ... },
  on_colors: { color1: '#FFFFFF', ... },
  accessibility_variants: { ... }
}

// Update color schema
POST /api/v1/admin/color-schema
Body: { colors: { color1: '#FF5733', ... } }
```

### User Color Preferences

```typescript
// Get user-specific colors
GET /api/v1/user/colors
Response: {
  colors: { ... },
  user_preferences: {
    use_accessible_colors: false,
    theme_mode: 'light'
  }
}

// Update accessibility preference
POST /api/v1/user/accessibility-preference
Body: { use_accessible_colors: true }
```

### Real-time Updates

WebSocket events for instant color synchronization:

```typescript
// Color schema updated event
{
  type: 'color_schema_updated',
  colors: { color1: '#FF5733', ... },
  event_type: 'admin_update',
  client_id: 1
}
```

## Implementation Guidelines

### Frontend Implementation

**React Components**
```tsx
// Use CSS variables for colors
const Button = ({ variant = 'primary' }) => (
  <button 
    className={`btn btn-${variant}`}
    style={{
      backgroundColor: `var(--color-${variant === 'primary' ? '1' : '2'})`,
      color: `var(--on-color-${variant === 'primary' ? '1' : '2'})`
    }}
  >
    Click me
  </button>
);
```

**CSS Classes**
```css
.btn-primary {
  background-color: var(--color-1);
  color: var(--on-color-1);
}

.gradient-header {
  background: linear-gradient(135deg, var(--color-1), var(--color-2));
  color: var(--on-gradient-1-2);
}
```

### ETL Service Implementation

**Template Integration**
```html
<!-- Color variables injected server-side -->
<style>
:root {
  --color-1: {{ color_schema.color1 }};
  --on-color-1: {{ color_schema.on_color1 }};
  /* ... */
}
</style>
```

### Backend Service Implementation

**Color Calculation Service**
```python
class ColorCalculationService:
    def calculate_on_color(self, background_color: str) -> str:
        """Calculate optimal text color for background"""
        luminance = self.get_relative_luminance(background_color)
        return '#FFFFFF' if luminance < 0.5 else '#000000'
    
    def calculate_contrast_ratio(self, color1: str, color2: str) -> float:
        """Calculate WCAG contrast ratio between two colors"""
        # Implementation details...
```

## Performance Optimization

### Caching Strategy

- **Client Colors**: 24-hour TTL (rarely change)
- **User Colors**: 15-minute TTL (may change with preferences)
- **Redis Keys**: Structured with client/user context
- **Cache Invalidation**: Automatic on color updates

### Loading Strategy

1. **First Paint**: Static CSS fallbacks prevent flash
2. **API Load**: Dynamic colors applied via CSS variables
3. **WebSocket**: Real-time updates for color changes
4. **Local Storage**: Cache last-used colors for faster loading

## Best Practices

### Do's
- ✅ Use CSS variables for all color references
- ✅ Store colors in database, not hardcoded
- ✅ Test color combinations for accessibility
- ✅ Provide user accessibility options
- ✅ Use semantic color names (primary, secondary, etc.)
- ✅ Implement proper caching strategies

### Don'ts
- ❌ Hardcode color values in components
- ❌ Use colors that fail WCAG compliance
- ❌ Ignore user accessibility preferences
- ❌ Skip color contrast testing
- ❌ Duplicate color logic across services
- ❌ Forget to handle theme switching

## Testing and Validation

### Accessibility Testing
- Automated contrast ratio validation
- Screen reader compatibility testing
- Color blindness simulation
- WCAG compliance verification

### Cross-browser Testing
- CSS variable support validation
- Color rendering consistency
- Performance impact assessment
- WebSocket functionality testing

## Future Enhancements

### Planned Features
- **Advanced Color Picker**: Visual admin interface with live preview
- **Color Analytics**: Usage tracking and optimization suggestions
- **Extended Palette**: Support for additional color slots
- **Brand Guidelines**: Automated brand compliance checking
- **Color Themes**: Predefined color combinations for different industries

### Accessibility Improvements
- **High Contrast Mode**: System-level high contrast support
- **Color Blind Support**: Enhanced color differentiation
- **Motion Preferences**: Respect user motion sensitivity
- **Font Size Integration**: Dynamic color adjustments based on font size

This design system ensures consistent, accessible, and performant color management across the entire Pulse Platform while providing flexibility for client branding and user preferences.
