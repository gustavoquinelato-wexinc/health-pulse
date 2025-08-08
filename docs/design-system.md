# Pulse Platform Design System: Color Strategy

This document defines the platform-wide color strategy, tokens, and behaviors across Frontend and ETL services.

## Goals
- Centralize brand colors in the database for per-client flexibility (default_color1..5, custom_color1..5)
- Provide contrast-aware “on” colors for text/icons: on-color-*, on-gradient-*
- Avoid hardcoded colors in UI code; use CSS variables
- Guarantee WCAG-compliant contrast without visual flash

## Token Model
- Base colors (per mode):
  - default_color1..5 (DB)
  - custom_color1..5 (DB)
- Derived tokens (computed):
  - default_on_color1..5 (DB)
  - default_on_gradient_1-2..4-5 (DB)
  - custom_on_color1..5 (DB)
  - custom_on_gradient_1-2..4-5 (DB)

Frontend/ETL map the active mode to CSS variables:
- --color-1..--color-5
- --on-color-1..--on-color-5
- --on-gradient-1-2, --on-gradient-2-3, --on-gradient-3-4, --on-gradient-4-5

## Server-side computation (backend)
- On palette save (custom mode): recompute custom_on_color* and custom_on_gradient_*-* using WCAG relative luminance.
- On seed/install: compute default_on_color* and default_on_gradient_*-* based on default palette.
- GET /api/v1/admin/color-schema returns: { mode, colors (active), default_colors, custom_colors, on_colors, on_gradients } filtered by client_id.

## Frontend behavior
- ThemeContext sets CSS vars at runtime:
  - --color-1..--color-5 from API colors
  - --on-color-* and --on-gradient-* from API; fallback to luminance if missing
- Minimal hardcoded colors exist only as first-paint fallback; overwritten once API data loads
- Utility classes:
  - .text-on-color-N, .text-on-gradient-X-Y
  - Opacity variants: -80/-60 (or use CSS color-mix variables)

## ETL behavior
- modern_layout injects script pre-paint to set --color-* and on-color variables using server-provided schema; falls back to luminance if missing
- CSS uses tokens for gradient/colored surfaces
- Error/legacy templates updated to avoid hardcoded white text on gradients

## First-paint fallback strategy
- Keep minimal static defaults in CSS to avoid unstyled content at T0
- Frontend: index.html reads last palette from localStorage and applies quickly; ThemeContext then applies API values
- ETL: server renders schema and sets CSS vars before paint

## WCAG computation details
- Relative luminance via sRGB linearization
- Contrast ratio (L1+0.05)/(L2+0.05) vs black/white; choose the higher ratio for solids
- For gradients, choose the text color maximizing the minimum contrast across both stops

## Usage guidelines
- Text over solid brand color N: color: var(--on-color-N)
- Text over gradient a→b: color: var(--on-gradient-a-b)
- Prefer tokens over hardcoded #fff/#000
- For softer text on gradients, use provided mix vars or -80/-60 utilities

## Do’s and Don’ts
- Do store and read all palettes from DB (system_settings)
- Do compute and persist on-colors server-side
- Do set CSS vars before paint to avoid flashes
- Don’t hardcode text-white on brand backgrounds
- Don’t duplicate color-mix inline; prefer shared vars/utilities

## Future enhancements
- Add admin UI to edit default_color* with recompute of default_on_* tokens
- Visual contrast preview in admin with WCAG ratios
- Expand gradient pairs beyond 1-2..4-5 if needed by design

