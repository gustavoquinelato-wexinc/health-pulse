# Pulse Platform Color System

## Overview

The Pulse Platform implements a standardized 5-color schema system that provides consistency across the platform while allowing client-specific customization. This system supports both light and dark modes with database persistence.

## 🎨 5-Color Schema System

### Core Concept
The platform uses exactly **5 colors** for all UI elements, ensuring:
- **Consistency**: Same color roles across all components
- **Flexibility**: Easy customization for different clients
- **Accessibility**: Proper contrast ratios in both light and dark modes
- **Scalability**: Simple system that works for any client branding

### Color Roles
1. **Color 1 (Primary)**: Main branding, primary actions, important CTAs
2. **Color 2 (Secondary)**: Secondary actions, navigation, supporting elements  
3. **Color 3 (Success)**: Success states, positive feedback, completed items
4. **Color 4 (Info)**: Information, neutral states, data visualization
5. **Color 5 (Warning)**: Warnings, alerts, attention-required items

## 🎯 Default Color Schema

### Professional Color Palette
```css
:root {
    --color-1: #2862EB;  /* Blue - Primary */
    --color-2: #763DED;  /* Purple - Secondary */
    --color-3: #059669;  /* Emerald - Success */
    --color-4: #0EA5E9;  /* Sky Blue - Info */
    --color-5: #F59E0B;  /* Amber - Warning */
}
```

### Usage Examples
```jsx
// Primary button
<button className="bg-color-1 text-white">Save Changes</button>

// Success notification
<div className="border-l-4 border-color-3 bg-green-50 p-4">
    <span className="text-color-3">✓ Successfully saved!</span>
</div>

// Warning alert
<div className="bg-color-5 text-white p-3 rounded">
    ⚠️ Please review your settings
</div>
```

## 🏢 Custom Color Schema (Client Branding)

### WEX Brand Colors
```css
[data-color-schema="custom"] {
    --color-1: #C8102E;  /* WEX Red */
    --color-2: #253746;  /* Dark Blue */
    --color-3: #00C7B1;  /* Teal */
    --color-4: #A2DDF8;  /* Light Blue */
    --color-5: #FFBF3F;  /* Yellow */
}
```

### Customization Process
1. **Admin Access**: Only admin users can modify color schemas
2. **Live Preview**: Changes are previewed in real-time
3. **Database Storage**: Custom colors stored in `system_settings` table
4. **Client-Specific**: Each client can have their own color schema
5. **Fallback**: Always falls back to default colors if custom colors fail

## 🌙 Light/Dark Mode Support

### Theme Variables
```css
/* Light Theme */
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #f1f5f9;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #64748b;
}

/* Dark Theme */
[data-theme="dark"] {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-tertiary: #334155;
    --text-primary: #f8fafc;
    --text-secondary: #cbd5e1;
    --text-muted: #94a3b8;
}
```

### Database Persistence
- **Setting Key**: `theme_mode` in `system_settings` table
- **Values**: `"light"` or `"dark"`
- **Per-Client**: Each client has independent theme preference
- **API Endpoints**: 
  - `GET /api/v1/admin/theme-mode` - Get current theme
  - `POST /api/v1/admin/theme-mode` - Save theme preference

## 🔧 Implementation Guidelines

### When to Use More Than 5 Colors
The 5-color system covers 95% of use cases. Use additional colors only when:
- **Data Visualization**: Charts requiring more than 5 data series
- **Status Systems**: Complex workflows with many states
- **Accessibility**: Additional colors needed for contrast compliance

### Component Development
```jsx
// ✅ Good: Use the 5-color system
function StatusBadge({ type, children }) {
    const colors = {
        primary: 'bg-color-1',
        secondary: 'bg-color-2', 
        success: 'bg-color-3',
        info: 'bg-color-4',
        warning: 'bg-color-5'
    }
    
    return (
        <span className={`${colors[type]} text-white px-2 py-1 rounded`}>
            {children}
        </span>
    )
}

// ❌ Avoid: Hardcoded colors
function BadExample() {
    return <div className="bg-red-500">Don't do this</div>
}
```

### CSS Best Practices
```css
/* ✅ Good: Use CSS custom properties */
.primary-button {
    background-color: var(--color-1);
    color: white;
}

/* ✅ Good: Use Tailwind color classes */
.success-message {
    @apply bg-color-3 text-white p-4 rounded;
}

/* ❌ Avoid: Hardcoded hex values */
.bad-example {
    background-color: #2862EB; /* Don't hardcode */
}
```

## 📊 Color Schema Management

### Admin Interface
- **Settings Page**: `/settings/color-scheme`
- **Mode Toggle**: Switch between default and custom colors
- **Color Picker**: Visual color selection with hex input
- **Live Preview**: Real-time preview of color changes
- **Apply/Reset**: Persist changes or revert to defaults

### Database Schema
```sql
-- Color schema mode setting
INSERT INTO system_settings (setting_key, setting_value, setting_type, description, client_id)
VALUES ('color_schema_mode', 'default', 'string', 'Color schema mode (default or custom)', 1);

-- Custom color settings
INSERT INTO system_settings (setting_key, setting_value, setting_type, description, client_id)
VALUES ('custom_color1', '#C8102E', 'string', 'Custom color 1 for color schema', 1);
-- ... repeat for custom_color2 through custom_color5
```

## 🎯 Migration and Compatibility

### Existing Components
When updating existing components to use the 5-color system:
1. **Audit Current Colors**: Identify all hardcoded colors
2. **Map to Roles**: Assign each color to one of the 5 roles
3. **Update Classes**: Replace hardcoded colors with color variables
4. **Test Both Modes**: Verify appearance in light and dark modes
5. **Test Custom Colors**: Ensure compatibility with client branding

### Legacy Support
- **Gradual Migration**: Components can be updated incrementally
- **Fallback Colors**: System gracefully handles missing custom colors
- **Backward Compatibility**: Existing color classes continue to work

## 📋 Quick Reference

### Available CSS Classes
```css
/* Background Colors */
.bg-color-1, .bg-color-2, .bg-color-3, .bg-color-4, .bg-color-5

/* Text Colors */
.text-color-1, .text-color-2, .text-color-3, .text-color-4, .text-color-5

/* Border Colors */
.border-color-1, .border-color-2, .border-color-3, .border-color-4, .border-color-5
```

### CSS Custom Properties
```css
var(--color-1)  /* Primary */
var(--color-2)  /* Secondary */
var(--color-3)  /* Success */
var(--color-4)  /* Info */
var(--color-5)  /* Warning */
```

### Theme Variables
```css
var(--bg-primary)     /* Main background */
var(--bg-secondary)   /* Secondary background */
var(--bg-tertiary)    /* Tertiary background */
var(--text-primary)   /* Primary text */
var(--text-secondary) /* Secondary text */
var(--text-muted)     /* Muted text */
```

---

**For implementation details, see:**
- [Frontend Design System](../services/frontend-app/docs/DESIGN_SYSTEM.md)
- [Frontend App Guide](ai_coaching_documents/04_frontend_app_guide.md)
- [Color Schema Settings Component](../services/frontend-app/src/components/ColorSchemaPanel.tsx)
