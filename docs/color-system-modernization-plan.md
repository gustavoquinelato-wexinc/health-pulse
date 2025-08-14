# Color System Modernization Plan

**Status**: Planning Phase
**Created**: 2025-01-13
**Updated**: 2025-01-13
**Objective**: Transform system_settings-based colors into modern, accessibility-ready, client-centric color management

---

## **Overview**
Transform the current system_settings-based color system into a modern, accessibility-ready, client-centric color management system with automatic calculations, theme-adaptive colors, and Redis caching for optimal performance.

## **Key Architectural Decisions**
- **Normalized two-table approach**: `client_color_settings` + `client_accessibility_colors` with clean separation
- **2 rows per client**: Each client has 'default' and 'custom' color_schema_mode entries (no column prefixes)
- **Storage-based with Redis caching**: Pre-calculated colors stored in database, cached in Redis for performance
- **Automatic calculations**: All color variants computed from base colors + settings during admin updates
- **Global default management**: Easy to update default colors for all clients simultaneously
- **Client-level accessibility**: Company-wide accessibility settings, user-level toggle
- **Simplified adaptive colors**: Single adaptive column + context flag (not light/dark duplicates)
- **New font threshold**: 0.5 luminance threshold for better UX
- **Performance-first**: Redis caching to avoid database JOINs on every request
- **Migration-ready**: Easy evolution path to hybrid/calculation-based approach later

---

## **PHASE 1: Database Foundation** 🗄️

### **Step 1.1: Create Tables and Populate Initial Data**
**Objective**: Add new tables and populate with calculated color data in single migration

**Tasks:**
- [ ] Add `client_color_settings` table to migration 001 (main colors)
- [ ] Add `client_accessibility_colors` table to migration 001 (accessibility variants)
- [ ] Add proper foreign keys and constraints
- [ ] Add indexes for performance and caching
- [ ] Create color calculation functions in migration 001
- [ ] Insert initial data for all existing clients with calculated colors
- [ ] Insert calculated values for _on, _gradient and _adaptive colors in both tables

**Files to modify:**
- `services/backend-service/scripts/migrations/001_initial_schema.py`

**Main Colors Table (Normalized - 2 rows per client):**
```sql
CREATE TABLE client_color_settings (
    id SERIAL PRIMARY KEY,

    -- === MODE IDENTIFIER ===
    color_schema_mode VARCHAR(10) NOT NULL, -- 'default' or 'custom'

    -- === SETTINGS (only in main table) ===
    font_contrast_threshold DECIMAL(3,2) DEFAULT 0.5,
    colors_defined_in_mode VARCHAR(5) DEFAULT 'light', -- 'light' or 'dark'

    -- === BASE COLORS (simplified - no prefixes) ===
    color1 VARCHAR(7),
    color2 VARCHAR(7),
    color3 VARCHAR(7),
    color4 VARCHAR(7),
    color5 VARCHAR(7),

    -- === AUTO-CALCULATED VARIANTS (simplified - no prefixes) ===
    -- On colors (5 columns)
    on_color1 VARCHAR(7),
    on_color2 VARCHAR(7),
    on_color3 VARCHAR(7),
    on_color4 VARCHAR(7),
    on_color5 VARCHAR(7),

    -- On gradient colors (5 columns)
    on_gradient_1_2 VARCHAR(7),
    on_gradient_2_3 VARCHAR(7),
    on_gradient_3_4 VARCHAR(7),
    on_gradient_4_5 VARCHAR(7),
    on_gradient_5_1 VARCHAR(7),

    -- Adaptive colors (5 columns) - for opposite theme
    adaptive_color1 VARCHAR(7),
    adaptive_color2 VARCHAR(7),
    adaptive_color3 VARCHAR(7),
    adaptive_color4 VARCHAR(7),
    adaptive_color5 VARCHAR(7),

    -- === BASE ENTITY FIELDS (at the end) ===
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_client_color_mode UNIQUE(client_id, color_schema_mode)
);

-- Index for fast lookups
CREATE INDEX idx_client_color_settings_client_id ON client_color_settings(client_id);
CREATE INDEX idx_client_color_settings_mode ON client_color_settings(client_id, color_schema_mode);

**Accessibility Colors Table (4 rows per client - same structure as main table):**
```sql
CREATE TABLE client_accessibility_colors (
    id SERIAL PRIMARY KEY,

    -- === MODE AND LEVEL IDENTIFIERS ===
    color_schema_mode VARCHAR(10) NOT NULL, -- 'default' or 'custom'
    accessibility_level VARCHAR(3) NOT NULL, -- 'AA', 'AAA'

    -- === ACCESSIBILITY SETTINGS (only in this table) ===
    contrast_ratio_normal DECIMAL(3,1) DEFAULT 4.5,
    contrast_ratio_large DECIMAL(3,1) DEFAULT 3.0,
    high_contrast_mode BOOLEAN DEFAULT FALSE,
    reduce_motion BOOLEAN DEFAULT FALSE,
    colorblind_safe_palette BOOLEAN DEFAULT FALSE,

    -- === BASE COLORS (simplified - no prefixes, same as main table) ===
    color1 VARCHAR(7),
    color2 VARCHAR(7),
    color3 VARCHAR(7),
    color4 VARCHAR(7),
    color5 VARCHAR(7),

    -- === AUTO-CALCULATED VARIANTS (simplified - no prefixes, same as main table) ===
    -- On colors (5 columns)
    on_color1 VARCHAR(7),
    on_color2 VARCHAR(7),
    on_color3 VARCHAR(7),
    on_color4 VARCHAR(7),
    on_color5 VARCHAR(7),

    -- On gradient colors (5 columns)
    on_gradient_1_2 VARCHAR(7),
    on_gradient_2_3 VARCHAR(7),
    on_gradient_3_4 VARCHAR(7),
    on_gradient_4_5 VARCHAR(7),
    on_gradient_5_1 VARCHAR(7),

    -- Adaptive colors (5 columns) - for opposite theme
    adaptive_color1 VARCHAR(7),
    adaptive_color2 VARCHAR(7),
    adaptive_color3 VARCHAR(7),
    adaptive_color4 VARCHAR(7),
    adaptive_color5 VARCHAR(7),

    -- === BASE ENTITY FIELDS (at the end) ===
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_client_accessibility_mode_level UNIQUE(client_id, color_schema_mode, accessibility_level)
);

-- Indexes for fast lookups
CREATE INDEX idx_client_accessibility_colors_client_id ON client_accessibility_colors(client_id);
CREATE INDEX idx_client_accessibility_colors_mode_level ON client_accessibility_colors(client_id, color_schema_mode, accessibility_level);
```

**Data Population Strategy (in same migration):**
```python
# Default color template (same for all clients)
DEFAULT_COLORS = {
    'color1': '#2862EB', 'color2': '#763DED', 'color3': '#059669',
    'color4': '#0EA5E9', 'color5': '#F59E0B'
}

# Custom colors per client
CUSTOM_COLORS = {
    'WEX': {'color1': '#C8102E', 'color2': '#253746', 'color3': '#00C7B1', 'color4': '#A2DDF8', 'color5': '#FFBF3F'},
    'Google': {'color1': '#4285F4', 'color2': '#34A853', 'color3': '#FBBC05', 'color4': '#EA4335', 'color5': '#9AA0A6'},
    'Apple': {'color1': '#007AFF', 'color2': '#34C759', 'color3': '#FF9500', 'color4': '#FF3B30', 'color5': '#8E8E93'}
}

# For each client - insert all data in single migration
for client_name, client_id in [('WEX', wex_id), ('Google', google_id), ('Apple', apple_id)]:
    # 1. Insert default mode row with calculated variants
    default_calculated = calculate_all_variants(DEFAULT_COLORS)
    insert_client_color_settings(client_id, 'default', default_calculated)

    # 2. Insert custom mode row with calculated variants
    custom_calculated = calculate_all_variants(CUSTOM_COLORS[client_name])
    insert_client_color_settings(client_id, 'custom', custom_calculated)

    # 3. Insert accessibility variants (4 rows per client: 2 modes × 2 levels)
    for mode in ['default', 'custom']:
        for level in ['AA', 'AAA']:
            base_colors = DEFAULT_COLORS if mode == 'default' else CUSTOM_COLORS[client_name]

            # Calculate accessibility-enhanced versions
            accessible_colors = {}
            for i in range(1, 6):
                accessible_colors[f'color{i}'] = calculate_accessible_color(base_colors[f'color{i}'], level)

            # Calculate all variants for accessibility-enhanced colors
            accessible_calculated = calculate_all_variants(accessible_colors)
            insert_client_accessibility_colors(client_id, mode, level, accessible_calculated)
```

**Expected Results:**
- **Main table**: 6 rows total (3 clients × 2 modes each)
- **Accessibility table**: 12 rows total (3 clients × 2 modes × 2 accessibility levels each)
- Green (#059669) and Blue (#0EA5E9) now get WHITE font (improved UX)
- All calculated colors (_on, _gradient, _adaptive) properly computed in both tables

**Validation:**
- [ ] Both tables created successfully
- [ ] Foreign key constraints work
- [ ] Unique constraints enforced
- [ ] Indexes created for performance
- [ ] All clients have 2 rows in main table (default + custom modes)
- [ ] All clients have 4 rows in accessibility table (2 modes × 2 levels)
- [ ] Default colors are identical across all clients (in both tables)
- [ ] Custom colors are unique per client (in both tables)
- [ ] All calculated colors (_on, _gradient, _adaptive) have correct values
- [ ] Both tables inherit BaseEntity pattern (active, created_at, last_updated_at)

### **Step 1.2: Update Unified Models for New Tables**
**Objective**: Add new color tables to unified_model classes in both services

**Tasks:**
- [ ] Add `ClientColorSettings` model to backend unified_model.py
- [ ] Add `ClientAccessibilityColors` model to backend unified_model.py
- [ ] Add `ClientColorSettings` model to ETL unified_model.py
- [ ] Add `ClientAccessibilityColors` model to ETL unified_model.py
- [ ] Ensure both models inherit from BaseEntity
- [ ] Add proper relationships and constraints

**Files to modify:**
- `services/backend-service/app/models/unified_model.py`
- `services/etl-service/app/models/unified_model.py`

**Model Definitions (Normalized):**
```python
class ClientColorSettings(BaseEntity):
    __tablename__ = 'client_color_settings'

    id = Column(Integer, primary_key=True)

    # Mode identifier
    color_schema_mode = Column(String(10), nullable=False)  # 'default' or 'custom'

    # Settings (only in main table)
    font_contrast_threshold = Column(Numeric(3,2), default=0.5)
    colors_defined_in_mode = Column(String(5), default='light')

    # Base colors (simplified - no prefixes)
    color1 = Column(String(7))
    color2 = Column(String(7))
    color3 = Column(String(7))
    color4 = Column(String(7))
    color5 = Column(String(7))

    # Computed variants (simplified - no prefixes)
    on_color1 = Column(String(7))
    on_color2 = Column(String(7))
    # ... etc for all computed colors

    # BaseEntity fields (at the end)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    # active, created_at, last_updated_at inherited from BaseEntity

    # Relationships
    client = relationship("Clients", back_populates="color_settings")
    accessibility_colors = relationship("ClientAccessibilityColors", back_populates="color_settings")

    __table_args__ = (
        UniqueConstraint('client_id', 'color_schema_mode'),
    )

class ClientAccessibilityColors(BaseEntity):
    __tablename__ = 'client_accessibility_colors'

    id = Column(Integer, primary_key=True)

    # Mode and level identifiers
    color_schema_mode = Column(String(10), nullable=False)  # 'default' or 'custom'
    accessibility_level = Column(String(3), nullable=False)  # 'AA', 'AAA'

    # Accessibility settings (only in this table)
    contrast_ratio_normal = Column(Numeric(3,1), default=4.5)
    contrast_ratio_large = Column(Numeric(3,1), default=3.0)
    high_contrast_mode = Column(Boolean, default=False)
    reduce_motion = Column(Boolean, default=False)
    colorblind_safe_palette = Column(Boolean, default=False)

    # Base colors (simplified - no prefixes, same as main table)
    color1 = Column(String(7))
    color2 = Column(String(7))
    color3 = Column(String(7))
    color4 = Column(String(7))
    color5 = Column(String(7))

    # Computed variants (simplified - no prefixes, same as main table)
    on_color1 = Column(String(7))
    on_color2 = Column(String(7))
    on_color3 = Column(String(7))
    on_color4 = Column(String(7))
    on_color5 = Column(String(7))

    on_gradient_1_2 = Column(String(7))
    on_gradient_2_3 = Column(String(7))
    on_gradient_3_4 = Column(String(7))
    on_gradient_4_5 = Column(String(7))
    on_gradient_5_1 = Column(String(7))

    adaptive_color1 = Column(String(7))
    adaptive_color2 = Column(String(7))
    adaptive_color3 = Column(String(7))
    adaptive_color4 = Column(String(7))
    adaptive_color5 = Column(String(7))

    # BaseEntity fields (at the end)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    # active, created_at, last_updated_at inherited from BaseEntity

    # Relationships
    client = relationship("Clients")
    color_settings = relationship("ClientColorSettings", back_populates="accessibility_colors")

    __table_args__ = (
        UniqueConstraint('client_id', 'color_schema_mode', 'accessibility_level'),
    )
```

**Validation:**
- [ ] Models added to both backend and ETL services
- [ ] Models inherit from BaseEntity correctly
- [ ] Relationships are properly defined
- [ ] Foreign key constraints work
- [ ] Models can be imported and used

### **Step 1.3: Create Color Calculation Functions**
**Objective**: Build calculation engine for all color variants (used in Step 1.1)

**Tasks:**
- [ ] Create `_luminance()` function (WCAG standard)
- [ ] Create `_pick_on_color_new_threshold()` (0.5 threshold)
- [ ] Create `_pick_on_gradient()` function
- [ ] Create `_get_adaptive_color()` function
- [ ] Create `_get_accessible_color()` functions (AA/AAA)
- [ ] Create `_lighten_color()` and `_darken_color()` helpers

**Key Functions:**
```python
def _luminance(hex_color):
    """Calculate WCAG relative luminance"""
    # Implementation with proper linearization

def _pick_on_color_new_threshold(hex_color):
    """Use new 0.5 threshold for font color selection"""
    luminance = _luminance(hex_color)
    return '#FFFFFF' if luminance < 0.5 else '#000000'

def _pick_on_gradient(color_a, color_b):
    """Choose best font color for gradient pair"""
    on_a = _pick_on_color_new_threshold(color_a)
    on_b = _pick_on_color_new_threshold(color_b)
    return on_a if on_a == on_b else '#FFFFFF'  # Default to white if different

def _pick_on_gradient(color_a, color_b):
    """Choose best font color for gradient pair"""
    on_a = _pick_on_color_new_threshold(color_a)
    on_b = _pick_on_color_new_threshold(color_b)
    return on_a if on_a == on_b else '#FFFFFF'  # Default to white if different

def _get_adaptive_color(hex_color, defined_in_mode='light'):
    """Create theme-adaptive color for opposite mode"""
    # Lighten dark colors for dark mode visibility
    # Darken light colors for light mode visibility

def calculate_all_variants(base_colors):
    """Calculate all color variants from base colors"""
    variants = {}

    # On colors
    for i in range(1, 6):
        variants[f'on_color{i}'] = _pick_on_color_new_threshold(base_colors[f'color{i}'])

    # On gradient colors (all 5 combinations including 5→1)
    gradient_pairs = [
        ('color1', 'color2', 'on_gradient_1_2'),
        ('color2', 'color3', 'on_gradient_2_3'),
        ('color3', 'color4', 'on_gradient_3_4'),
        ('color4', 'color5', 'on_gradient_4_5'),
        ('color5', 'color1', 'on_gradient_5_1')  # Wraps back to color1
    ]

    for color_a_key, color_b_key, gradient_key in gradient_pairs:
        variants[gradient_key] = _pick_on_gradient(base_colors[color_a_key], base_colors[color_b_key])

    # Adaptive colors
    for i in range(1, 6):
        variants[f'adaptive_color{i}'] = _get_adaptive_color(base_colors[f'color{i}'])

    return variants

def calculate_all_variants(base_colors):
    """Calculate all color variants from base colors"""
    variants = {}

    # On colors
    for i in range(1, 6):
        variants[f'on_color{i}'] = _pick_on_color_new_threshold(base_colors[f'color{i}'])

    # On gradient colors (all 5 combinations including 5→1)
    gradient_pairs = [
        ('color1', 'color2', 'on_gradient_1_2'),
        ('color2', 'color3', 'on_gradient_2_3'),
        ('color3', 'color4', 'on_gradient_3_4'),
        ('color4', 'color5', 'on_gradient_4_5'),
        ('color5', 'color1', 'on_gradient_5_1')  # Wraps back to color1
    ]

    for color_a_key, color_b_key, gradient_key in gradient_pairs:
        variants[gradient_key] = _pick_on_gradient(base_colors[color_a_key], base_colors[color_b_key])

    # Adaptive colors
    for i in range(1, 6):
        variants[f'adaptive_color{i}'] = _get_adaptive_color(base_colors[f'color{i}'])

    return variants
```

**Files to modify:**
- `services/backend-service/scripts/migrations/001_initial_schema.py`

**Validation:**
- [ ] Functions calculate correct luminance values
- [ ] New 0.5 threshold produces expected results
- [ ] Adaptive colors work for both light/dark contexts



---

## **PHASE 2: Backend Services & Redis Caching** 🔧

### **Step 2.1: Create Color Management & Caching Services**
**Objective**: Build service layer with Redis caching for optimal performance

**Tasks:**
- [ ] Create `ColorCalculationService` class for color computations
- [ ] Create `ColorCacheService` class for Redis caching
- [ ] Create `ColorResolutionService` class for user-specific color resolution
- [ ] Implement database query optimization with single JOIN
- [ ] Add validation for color hex values

**Files to create/modify:**
- `services/backend-service/app/services/color_calculation_service.py`
- `services/backend-service/app/services/color_cache_service.py`
- `services/backend-service/app/services/color_resolution_service.py`

**ColorCacheService (Redis Integration):**
```python
class ColorCacheService:
    async def get_client_colors(self, client_id):
        """Get client colors from Redis cache or database"""
        cache_key = f"client_colors:{client_id}"

        # Try Redis first
        cached = await redis.get(cache_key)
        if cached and self.is_cache_fresh(cached):
            return json.loads(cached)

        # Fetch from database with optimized JOIN
        colors = await self.fetch_from_database(client_id)

        # Cache for 1 hour
        await redis.setex(cache_key, 3600, json.dumps(colors))
        return colors

    async def invalidate_client_colors(self, client_id):
        """Invalidate all caches for a client"""
        await redis.delete(f"client_colors:{client_id}")
        # Also invalidate user-specific caches
        user_keys = await redis.keys(f"user_colors:*:{client_id}:*")
        if user_keys:
            await redis.delete(*user_keys)
```

**ColorResolutionService (User-Specific Colors):**
```python
class ColorResolutionService:
    async def get_user_colors(self, user_id, theme='light'):
        """Get resolved colors for specific user with caching"""
        user = await get_user(user_id)
        cache_key = f"user_colors:{user_id}:{user.client_id}:{theme}"

        # Try user-specific cache
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Get client colors and resolve for user
        client_colors = await self.color_cache_service.get_client_colors(user.client_id)
        resolved = self.resolve_user_colors(client_colors, user.use_accessible_colors, theme)

        # Cache for 30 minutes
        await redis.setex(cache_key, 1800, json.dumps(resolved))
        return resolved
```

**Database Query Optimization (Normalized):**
```sql
-- Single optimized query to get all color data for a client
SELECT
    ccs.*,
    json_agg(
        json_build_object(
            'level', acc.accessibility_level,
            'mode', acc.color_schema_mode,
            'position', acc.color_position,
            'color', acc.accessible_color,
            'contrast_ratio', acc.contrast_ratio
        )
    ) FILTER (WHERE acc.id IS NOT NULL) as accessibility_colors
FROM client_color_settings ccs
LEFT JOIN client_accessibility_colors acc ON ccs.client_id = acc.client_id
WHERE ccs.client_id = $1
GROUP BY ccs.id, ccs.color_schema_mode
ORDER BY ccs.color_schema_mode;

-- Get specific mode colors (even faster)
SELECT * FROM client_color_settings
WHERE client_id = $1 AND color_schema_mode = $2;
```

**Validation:**
- [ ] Redis caching works correctly
- [ ] Cache invalidation works on updates
- [ ] Database queries are optimized (single JOIN)
- [ ] User-specific color resolution works
- [ ] Performance improvement measurable (>70% faster)

### **Step 2.2: Update Color Schema API Endpoints with Caching**
**Objective**: Modify existing APIs to use new tables with Redis caching

**Tasks:**
- [ ] Update `GET /api/v1/admin/color-schema` to use ColorCacheService
- [ ] Update `POST /api/v1/admin/color-schema` to write to both tables + invalidate cache
- [ ] Maintain backward compatibility with existing payload structure
- [ ] Add new fields (accessibility_level, colors_defined_in_mode)
- [ ] Implement cache invalidation on updates

**Files to modify:**
- `services/backend-service/app/api/admin_routes.py`

**Updated GET Endpoint:**
```python
@admin_routes.route('/color-schema', methods=['GET'])
async def get_color_schema():
    user = get_current_user()

    # Use caching service instead of direct database query
    colors = await color_cache_service.get_client_colors(user.client_id)

    return {
        "success": True,
        "mode": colors["color_schema_mode"],
        "colors": colors["active_colors"],
        "settings": {
            "font_contrast_threshold": colors["font_contrast_threshold"],
            "accessibility_level": colors["accessibility_level"],
            "colors_defined_in_mode": colors["colors_defined_in_mode"]
        },
        "computed_colors": {
            "on_colors": colors["on_colors"],
            "adaptive_colors": colors["adaptive_colors"]
        },
        "accessibility_colors": colors["accessibility_colors"]
    }
```

**Updated POST Endpoint:**
```python
@admin_routes.route('/color-schema', methods=['POST'])
async def update_color_schema():
    user = get_current_user()
    data = request.get_json()

    # 1. Update both database tables
    await update_client_color_settings(user.client_id, data)
    await update_client_accessibility_colors(user.client_id, data)

    # 2. Invalidate all related caches
    await color_cache_service.invalidate_client_colors(user.client_id)

    # 3. Notify connected users
    websocket.broadcast(f"client:{user.client_id}", {
        "type": "COLORS_UPDATED",
        "timestamp": datetime.utcnow().isoformat()
    })

    return {"success": True}
```

**Cache Invalidation Strategy:**
```python
async def invalidate_client_colors(client_id):
    """Comprehensive cache invalidation"""
    # Client-level cache
    await redis.delete(f"client_colors:{client_id}")

    # User-specific caches
    user_keys = await redis.keys(f"user_colors:*:{client_id}:*")
    if user_keys:
        await redis.delete(*user_keys)

    # ETL service cache (if applicable)
    await redis.delete(f"etl_colors:{client_id}")
```

**Validation:**
- [ ] Existing frontend continues to work
- [ ] New fields are properly returned
- [ ] Color updates trigger cache invalidation
- [ ] Performance improvement measurable
- [ ] WebSocket notifications work

### **Step 2.3: Add User Accessibility Preference**
**Objective**: Add user-level accessibility toggle

**Tasks:**
- [ ] Add `use_accessible_colors` column to users table
- [ ] Update user profile API to include accessibility preference
- [ ] Modify color resolution logic to consider user preference

**Files to modify:**
- `services/backend-service/scripts/migrations/001_initial_schema.py`
- `services/backend-service/app/api/auth_routes.py`

**User Table Addition:**
```sql
ALTER TABLE users ADD COLUMN (
    use_accessible_colors BOOLEAN DEFAULT FALSE
);
```

**Validation:**
- [ ] Users can toggle accessibility preference
- [ ] Color resolution respects user preference
- [ ] Default is false for existing users

---

## **PHASE 3: Frontend Color Schema Page** 🎨

### **Step 3.1: Update Color Schema Admin Interface**
**Objective**: Modernize admin UI for new color system

**Tasks:**
- [ ] Add accessibility level dropdown (A/AA/AAA)
- [ ] Add "Colors Defined In" toggle (Light/Dark)
- [ ] Add font contrast threshold display (read-only, auto-calculated)
- [ ] Add preview section for accessible color variants
- [ ] Update save logic to trigger recalculation

**Files to modify:**
- `services/frontend-app/src/components/ColorSchemaPanel.tsx`

**New UI Elements:**
```
┌─ Color Schema Settings ──────────────────────┐
│                                              │
│ Base Colors: [Color Picker UI]              │
│                                              │
│ Colors Defined In: ● Light ○ Dark           │
│                                              │
│ Accessibility Level: [AA ▼]                 │
│ ├─ Font Contrast: 0.5 (auto-calculated)     │
│ └─ [Preview accessible colors]              │
│                                              │
│ [Save] ← Triggers full recalculation        │
└──────────────────────────────────────────────┘
```

**Validation:**
- [ ] UI shows all new options
- [ ] Changing accessibility level updates preview
- [ ] Save triggers backend recalculation
- [ ] Loading states work properly

### **Step 3.2: Add User Accessibility Preference UI**
**Objective**: Add user-level accessibility toggle

**Tasks:**
- [ ] Add accessibility toggle to user profile/settings
- [ ] Add explanation text about company accessibility colors
- [ ] Update user profile save logic

**Files to modify:**
- `services/frontend-app/src/pages/ProfilePage.tsx` (or equivalent)

**New UI:**
```
┌─ Accessibility Preferences ──────────────────┐
│                                              │
│ Use High-Contrast Colors: [□]               │
│ (Uses your company's accessible color set)  │
│                                              │
└──────────────────────────────────────────────┘
```

**Validation:**
- [ ] Users can toggle accessibility preference
- [ ] Changes save properly
- [ ] UI updates immediately after save

---

## **PHASE 4: Frontend Integration with Caching** 🔄

### **Step 4.1: Update ThemeContext with User-Specific Color Resolution**
**Objective**: Integrate cached color system into theme context

**Tasks:**
- [ ] Modify ThemeContext to use new user-specific color API
- [ ] Add logic to resolve adaptive vs accessible colors based on user preference
- [ ] Update CSS variable setting to include all new variants
- [ ] Add `--adaptive-color-1` through `--adaptive-color-5` variables
- [ ] Implement real-time color updates via WebSocket

**Files to modify:**
- `services/frontend-app/src/contexts/ThemeContext.tsx`

**Updated ThemeContext:**
```javascript
const ThemeContext = createContext()

export const ThemeProvider = ({ children }) => {
    const [colors, setColors] = useState(null)
    const [theme, setTheme] = useState('light')
    const { user } = useAuth()

    // Load user-specific colors (cached on backend)
    const loadColors = useCallback(async () => {
        if (!user) return

        try {
            const response = await axios.get(`/api/v1/users/colors?theme=${theme}`)
            setColors(response.data)
        } catch (error) {
            console.error('Failed to load colors:', error)
            // Fallback to default colors
            setColors(getDefaultColors())
        }
    }, [user, theme])

    // Set CSS variables from cached/resolved colors
    useEffect(() => {
        if (!colors) return

        const root = document.documentElement

        // Set base colors
        Object.entries(colors.active_colors).forEach(([key, value]) => {
            root.style.setProperty(`--${key.replace('_', '-')}`, value)
        })

        // Set on colors
        Object.entries(colors.on_colors).forEach(([key, value]) => {
            root.style.setProperty(`--${key.replace('_', '-')}`, value)
        })

        // Set adaptive colors
        Object.entries(colors.adaptive_colors).forEach(([key, value]) => {
            root.style.setProperty(`--${key.replace('_', '-')}`, value)
        })

        // Set accessibility colors (if user has preference enabled)
        if (colors.accessibility_colors) {
            Object.entries(colors.accessibility_colors).forEach(([key, value]) => {
                root.style.setProperty(`--accessible-${key.replace('_', '-')}`, value)
            })
        }
    }, [colors])

    // Listen for real-time color updates
    useEffect(() => {
        if (!user) return

        const handleColorUpdate = () => {
            loadColors() // Reload colors when admin updates them
        }

        websocket.on(`client:${user.client_id}`, handleColorUpdate)
        return () => websocket.off(`client:${user.client_id}`, handleColorUpdate)
    }, [user, loadColors])

    return (
        <ThemeContext.Provider value={{ theme, setTheme, colors, loadColors }}>
            {children}
        </ThemeContext.Provider>
    )
}
```

**New CSS Variables Available:**
```css
/* Base colors (resolved based on user preferences) */
--color-1, --color-2, --color-3, --color-4, --color-5

/* On colors (for text/icons) */
--on-color-1, --on-color-2, --on-color-3, --on-color-4, --on-color-5

/* Adaptive colors (theme-aware) */
--adaptive-color-1, --adaptive-color-2, --adaptive-color-3, --adaptive-color-4, --adaptive-color-5

/* Accessible colors (if user preference enabled) */
--accessible-color-1, --accessible-color-2, --accessible-color-3, --accessible-color-4, --accessible-color-5
```

**Validation:**
- [ ] CSS variables are set correctly from cached data
- [ ] Theme switching triggers color reload
- [ ] User accessibility preference affects color resolution
- [ ] Real-time updates work when admin changes colors
- [ ] Performance is improved (cached colors load faster)

### **Step 4.2: Update ETL Service with Caching Integration**
**Objective**: Ensure ETL service uses cached color system

**Tasks:**
- [ ] Update ETL color schema manager to use cached color API
- [ ] Implement ETL-specific color caching
- [ ] Modify ETL template color variable setting
- [ ] Add WebSocket listener for real-time color updates
- [ ] Test color consistency between frontend and ETL

**Files to modify:**
- `services/etl-service/app/core/color_schema_manager.py`
- `services/etl-service/app/templates/layouts/modern_layout.html`

**Updated ETL Color Manager:**
```python
class ColorSchemaManager:
    def __init__(self):
        self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        self.cache_ttl = 3600  # 1 hour

    async def get_user_colors(self, user_id, theme='light'):
        """Get cached colors for ETL user"""
        cache_key = f"etl_user_colors:{user_id}:{theme}"

        # Try ETL-specific cache first
        cached = await self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Fall back to backend API
        try:
            response = await httpx.get(
                f"{BACKEND_URL}/api/v1/users/colors?theme={theme}",
                headers={"Authorization": f"Bearer {get_user_token(user_id)}"}
            )
            colors = response.json()

            # Cache in ETL-specific cache
            await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(colors))
            return colors

        except Exception as e:
            logger.error(f"Failed to load colors for user {user_id}: {e}")
            return self.get_fallback_colors()

    def invalidate_user_colors(self, user_id):
        """Invalidate ETL color cache for user"""
        pattern = f"etl_user_colors:{user_id}:*"
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)
```

**ETL Template Integration:**
```html
<!-- In modern_layout.html -->
<script>
    // Set CSS variables from cached colors
    const colors = {{ user_colors | tojsonfilter }};
    const root = document.documentElement;

    // Set all color variables
    Object.entries(colors.active_colors).forEach(([key, value]) => {
        root.style.setProperty(`--${key.replace('_', '-')}`, value);
    });

    // Listen for real-time updates
    websocket.on('client:{{ current_user.client_id }}', function(data) {
        if (data.type === 'COLORS_UPDATED') {
            location.reload(); // Simple approach - reload page
        }
    });
</script>
```

**Validation:**
- [ ] ETL colors match frontend colors exactly
- [ ] ETL color caching works independently
- [ ] Theme switching works in ETL
- [ ] Real-time updates work in ETL
- [ ] Performance is improved with caching

---

## **PHASE 5: Component Adaptation** 🎯

### **Step 5.1: Update DORA Metrics Cards**
**Objective**: Use adaptive colors in DORA cards

**Tasks:**
- [ ] Replace `var(--color-X)` with `var(--adaptive-color-X)` in gradients
- [ ] Update border colors to use adaptive variants
- [ ] Test visibility in both light and dark modes

**Files to modify:**
- `services/frontend-app/src/pages/DoraOverviewPage.tsx`

**Changes:**
```javascript
// Before
gradient: 'linear-gradient(135deg, var(--color-1) 0%, var(--color-2) 100%)',
borderColor: 'var(--color-1)',

// After  
gradient: 'linear-gradient(135deg, var(--adaptive-color-1) 0%, var(--adaptive-color-2) 100%)',
borderColor: 'var(--adaptive-color-1)',
```

**Validation:**
- [ ] Cards are visible in both themes
- [ ] Colors adapt properly to theme changes
- [ ] Accessibility preference affects card colors

### **Step 5.2: Update Chart Components**
**Objective**: Use adaptive colors in all charts

**Tasks:**
- [ ] Update DoraTrendChart to use adaptive colors
- [ ] Replace chart-safe color functions with CSS variables
- [ ] Update gradient definitions to use adaptive colors
- [ ] Test chart visibility across themes

**Files to modify:**
- `services/frontend-app/src/components/DoraTrendChart.tsx`

**Changes:**
```javascript
// Remove custom getChartSafeColor function
// Replace with CSS variables
stroke={getComputedColor('--adaptive-color-1', '#C8102E')}
```

**Validation:**
- [ ] Charts are visible in both themes
- [ ] Gradients work properly
- [ ] Performance is not degraded

### **Step 5.3: Update Other UI Components**
**Objective**: Apply adaptive colors throughout the platform

**Tasks:**
- [ ] Audit all components using `var(--color-X)`
- [ ] Update buttons, badges, progress bars to use adaptive colors
- [ ] Update any hardcoded color references
- [ ] Test accessibility compliance

**Components to Update:**
- Buttons with brand colors
- Status badges
- Progress indicators
- Navigation elements
- Any custom colored elements

**Validation:**
- [ ] All components are theme-aware
- [ ] Accessibility preference works everywhere
- [ ] No visual regressions

---

## **PHASE 6: Documentation & Cleanup** 📚

### **Step 6.1: Update Design System Documentation**
**Objective**: Document new color system architecture

**Tasks:**
- [ ] Update `docs/design-system.md` with new architecture
- [ ] Document color calculation formulas
- [ ] Add accessibility compliance information
- [ ] Document CSS variable naming conventions

**Files to modify:**
- `docs/design-system.md`
- `services/frontend-app/docs/design-system.md`

**Documentation Sections:**
- Color calculation algorithms
- Accessibility compliance levels
- CSS variable reference
- Migration guide from old system

**Validation:**
- [ ] Documentation is comprehensive
- [ ] Examples are accurate
- [ ] Migration guide is clear

### **Step 6.2: Remove Legacy System Settings & Optimize Caching**
**Objective**: Clean up old color-related system_settings and optimize Redis usage

**Tasks:**
- [ ] Remove color-related entries from system_settings table inserts in migration 001
- [ ] Update any remaining references to old color system
- [ ] Optimize Redis cache keys and TTL values
- [ ] Add cache monitoring and metrics
- [ ] Add migration notes for future reference

**System Settings Entries to Remove from Migration 001:**
- All `default_color*` entries from system_settings_data
- All `custom_color*` entries from system_settings_data
- All `*_on_color*` entries from system_settings_data
- All `*_on_gradient*` entries from system_settings_data
- `color_schema_mode` setting from system_settings_data

**Migration 001 Cleanup:**
```python
# Remove these entries from system_settings_data list:
# {"setting_key": "color_schema_mode", "setting_value": "default", ...},
# {"setting_key": "default_color1", "setting_value": "#2862EB", ...},
# {"setting_key": "default_color2", "setting_value": "#763DED", ...},
# ... all color-related entries
# {"setting_key": "default_on_color1", "setting_value": "#FFFFFF", ...},
# ... all on-color entries
# {"setting_key": "default_on_gradient_1_2", "setting_value": "#FFFFFF", ...},
# ... all gradient entries

# Keep only non-color system_settings entries
system_settings_data = [
    {"setting_key": "theme_mode", "setting_value": "light", ...},
    {"setting_key": "app_name", "setting_value": "Pulse Platform", ...},
    # ... other non-color settings
]
```

**Cache Optimization:**
```python
# Optimized cache structure
CACHE_KEYS = {
    'client_colors': 'client_colors:{client_id}',           # TTL: 1 hour
    'user_colors': 'user_colors:{user_id}:{client_id}:{theme}',  # TTL: 30 minutes
    'etl_colors': 'etl_user_colors:{user_id}:{theme}',     # TTL: 30 minutes
}

CACHE_TTL = {
    'client_colors': 3600,      # 1 hour (changes rarely)
    'user_colors': 1800,        # 30 minutes (user-specific)
    'etl_colors': 1800,         # 30 minutes (ETL-specific)
}

# Cache monitoring
async def get_cache_stats():
    """Monitor cache hit rates and performance"""
    stats = {
        'client_colors_hits': await redis.get('cache_hits:client_colors') or 0,
        'client_colors_misses': await redis.get('cache_misses:client_colors') or 0,
        'user_colors_hits': await redis.get('cache_hits:user_colors') or 0,
        'user_colors_misses': await redis.get('cache_misses:user_colors') or 0,
    }
    return stats
```

**Files to modify:**
- `services/backend-service/scripts/migrations/001_initial_schema.py`
- `services/backend-service/app/services/color_cache_service.py`

**Validation:**
- [ ] No orphaned color settings remain in system_settings
- [ ] All color-related system_settings entries removed from migration 001
- [ ] System works entirely on new color tables
- [ ] Redis cache performance is optimal
- [ ] Cache hit rates are >90% after warmup
- [ ] No performance regressions
- [ ] Migration 001 is clean and only contains non-color system_settings

---

## **PHASE 7: Testing & Validation** ✅

### **Step 7.1: Comprehensive Testing**
**Objective**: Ensure system works across all scenarios

**Test Scenarios:**
- [ ] Test all accessibility levels (A/AA/AAA)
- [ ] Test color definition in both light and dark modes
- [ ] Test user accessibility preference toggle
- [ ] Test theme switching with adaptive colors
- [ ] Test color schema changes and recalculation
- [ ] Test performance with multiple clients
- [ ] Test edge cases (invalid colors, missing data)

**Validation:**
- [ ] All color combinations are visible
- [ ] Performance is acceptable
- [ ] No visual regressions
- [ ] Accessibility compliance is maintained

### **Step 7.2: Documentation Review**
**Objective**: Ensure documentation is complete and accurate

**Tasks:**
- [ ] Review all updated documentation
- [ ] Test documentation examples
- [ ] Update any missing information
- [ ] Create troubleshooting guide

**Validation:**
- [ ] Documentation matches implementation
- [ ] Examples work as described
- [ ] Migration path is clear

---

## **Risk Mitigation Strategies**

### **Rollback Plan:**
- Keep system_settings color entries until Phase 6
- Implement feature flags for new color system
- Redis cache can be disabled to fall back to database-only
- Test thoroughly in development before production

### **Performance Considerations:**
- Index both color tables properly for fast JOINs
- Redis caching reduces database load by >90%
- Monitor cache hit rates and API response times
- Implement cache warming for active users
- Set up Redis monitoring and alerting

### **Compatibility:**
- Maintain backward compatibility until Phase 6
- Test with all existing clients
- Ensure ETL and Frontend stay in sync
- Redis failure should not break the system (graceful degradation)

### **Caching Risks & Mitigation:**
- **Cache invalidation bugs**: Comprehensive testing of all update scenarios
- **Redis failure**: Graceful fallback to database queries
- **Memory usage**: Monitor Redis memory and implement cache eviction policies
- **Cache consistency**: Use proper TTL values and invalidation strategies

---

## **Success Criteria**

- [ ] All colors are automatically calculated from base colors + settings
- [ ] Users can toggle accessibility colors without affecting others
- [ ] Admins can change accessibility level and see immediate recalculation
- [ ] Colors adapt properly between light and dark themes
- [ ] **Performance is significantly improved** (>70% faster color loading)
- [ ] **Redis caching works reliably** with >90% cache hit rate
- [ ] **Database load is reduced** by >90% for color requests
- [ ] Real-time color updates work via WebSocket
- [ ] Documentation is comprehensive and accurate
- [ ] No visual regressions in any component
- [ ] System gracefully handles Redis failures

**Performance Targets:**
- Color loading: <50ms (vs current ~200ms)
- Cache hit rate: >90% after warmup
- Database color queries: <10% of total requests
- Memory usage: <100MB Redis for color caching

**Estimated Timeline: 2-3 weeks for full implementation**

---

## **Progress Tracking**

### **Current Status**: Planning Complete ✅
### **Next Step**: Begin Phase 1.1 - Create Two-Table Color Structure

**Notes:**
- Plan updated for storage-based approach with Redis caching
- Two-table architecture for clean separation of concerns
- Redis caching strategy for optimal performance
- All architectural decisions documented
- Risk mitigation strategies in place
- Ready to begin implementation

**Key Changes from Original Plan:**
- ✅ **Normalized two-table approach** (main colors + accessibility colors)
- ✅ **2 rows per client** (default + custom modes, no column prefixes)
- ✅ **50% fewer columns** (simplified schema without default_/custom_ prefixes)
- ✅ **Global default management** (easy to update defaults for all clients)
- ✅ **Both tables inherit from BaseEntity** (active, created_at, last_updated_at)
- ✅ **Added Step 1.2** for unified_model updates in both services
- ✅ **Redis caching** for performance optimization
- ✅ **User-specific color resolution** with caching
- ✅ **Real-time updates** via WebSocket
- ✅ **Graceful fallback strategies**
- ✅ **Performance targets and monitoring**
- ✅ **Complete cleanup** of system_settings color entries in migration 001

---

*This document will be updated as we progress through each phase.*
