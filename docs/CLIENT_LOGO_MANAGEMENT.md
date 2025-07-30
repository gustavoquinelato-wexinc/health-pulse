# Client Logo Management

This document describes the client logo management system implemented in the Pulse Platform.

## Overview

The Pulse Platform uses a hybrid approach for client logo management:
- **Database**: Stores logo filename in `clients.logo_filename` column
- **File System**: Stores actual logo files in `services/frontend-app/public/assets/client-logos/`
- **Frontend**: Serves logos directly via static file serving

## Database Schema

### Clients Table
```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    website VARCHAR,
    logo_filename VARCHAR(255) DEFAULT 'default-logo.png',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);
```

### Example Data
```sql
INSERT INTO clients (name, website, logo_filename) VALUES
('WEX', 'https://www.wexinc.com', 'wex-logo.png'),
('TechCorp', 'https://www.techcorp.com', 'techcorp-logo.png');
```

## File Structure

```
services/frontend-app/public/assets/client-logos/
├── default-logo.png      # Fallback logo
├── wex-logo.png         # WEX client logo  
├── techcorp-logo.png    # TechCorp client logo
└── README.md            # Logo requirements
```

## API Endpoints (Future Implementation)

### Get Client Logo
```http
GET /api/v1/clients/:id/logo
```
**Response:**
```json
{
  "logo_url": "/assets/client-logos/wex-logo.png",
  "filename": "wex-logo.png",
  "client_id": 1
}
```

### Upload Client Logo
```http
POST /api/v1/clients/:id/logo
Content-Type: multipart/form-data

{
  "logo": <file>
}
```
**Response:**
```json
{
  "success": true,
  "filename": "wex-logo.png",
  "message": "Logo uploaded successfully"
}
```

### Reset to Default Logo
```http
DELETE /api/v1/clients/:id/logo
```
**Response:**
```json
{
  "success": true,
  "filename": "default-logo.png",
  "message": "Logo reset to default"
}
```

## Frontend Integration

### React Component Example
```jsx
import React from 'react';

const ClientLogo = ({ client, className = "h-12 w-auto" }) => {
  const logoPath = `/assets/client-logos/${client.logo_filename || 'default-logo.png'}`;
  
  return (
    <img 
      src={logoPath} 
      alt={`${client.name} Logo`}
      className={className}
      onError={(e) => {
        // Fallback to default logo if file not found
        e.target.src = '/assets/client-logos/default-logo.png';
      }}
    />
  );
};

export default ClientLogo;
```

### Usage in Header Component
```jsx
const Header = ({ currentClient }) => {
  return (
    <header className="flex items-center justify-between p-4">
      <div className="flex items-center space-x-3">
        <ClientLogo client={currentClient} className="h-10 w-auto" />
        <h1 className="text-xl font-semibold">{currentClient.name} Dashboard</h1>
      </div>
      {/* Other header content */}
    </header>
  );
};
```

## Logo Requirements

### Technical Specifications
- **Formats**: PNG (preferred), JPG, SVG
- **Size**: 200x200px (square) or 300x100px (rectangular)
- **Max File Size**: 2MB
- **Background**: Transparent (PNG) or white

### Naming Convention
- Format: `{client-name-slug}-logo.{ext}`
- Use lowercase with hyphens
- Examples: `wex-logo.png`, `techcorp-logo.png`

## Implementation Status

### ✅ Completed
- Database schema with `logo_filename` column
- Client models updated in both services
- Migration 001 includes logo setup for WEX and TechCorp
- File directory structure created
- Documentation and README files

### 🔄 Future Enhancements
- Backend API endpoints for logo upload/management
- Frontend admin interface for logo management
- Image validation and resizing
- Logo versioning and history
- CDN integration for production

## Security Considerations

1. **File Validation**: Validate file type, size, and content
2. **Path Traversal**: Sanitize filenames to prevent directory traversal
3. **Access Control**: Restrict logo upload to admin users
4. **File Cleanup**: Remove old logo files when updating

## Performance Considerations

1. **Static Serving**: Logos served directly by web server (not through application)
2. **Caching**: Set appropriate cache headers for logo files
3. **Optimization**: Consider image optimization for web delivery
4. **CDN**: Use CDN for production deployments with multiple clients

## Migration Notes

The logo functionality is included in Migration 001, which:
- Creates the `logo_filename` column with default value
- Sets up WEX and TechCorp with their respective logo filenames
- Maintains backward compatibility with existing clients
