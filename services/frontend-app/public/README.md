# Frontend Static Assets

This directory contains static assets that are served directly by the Vite development server and included in the production build.

## Directory Structure

```
public/
├── assets/                 # Client-specific assets
│   ├── wex/               # WEX client assets
│   │   ├── users/         # User profile images
│   │   └── logo.png       # WEX logo (add your actual logo here)
│   ├── apple/             # Apple client assets
│   └── google/            # Google client assets
├── wex-logo-image.png     # Default fallback logo (add your actual logo here)
└── favicon.ico            # Site favicon (add your actual favicon here)
```

## Adding Images

1. **Client Logos**: Place client-specific logos in `/assets/[client-name]/logo.png`
2. **Default Logo**: Replace `wex-logo-image.png` with your actual WEX logo
3. **User Profile Images**: Will be automatically stored in `/assets/[client]/users/[email]/[filename]`
4. **Favicon**: Add your site favicon as `favicon.ico`

## Image Requirements

- **Logos**: PNG format, recommended size 120x40px or similar aspect ratio
- **Profile Images**: PNG/JPG format, recommended size 200x200px (square)
- **Favicon**: ICO format, 16x16px and 32x32px sizes

## Notes

- All files in this directory are publicly accessible
- Images are served with cache-busting timestamps to prevent browser caching issues
- The frontend expects specific file paths, so maintain the directory structure
