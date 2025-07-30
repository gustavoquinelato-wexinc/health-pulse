# AI Coaching Documents

This directory contains domain-specific guidance documents for AI assistants working on the Pulse Platform. Each document provides detailed context, patterns, and best practices for specific areas of the platform.

## 📁 Document Structure

### 🌐 [Cross-Domain Guide](./01_cross_domain_guide.md)
**Scope**: Platform-wide concerns that affect all services
- **Authentication & Authorization**: Centralized auth system, JWT tokens, session management
- **Database Architecture**: Unified models, relationships, migration patterns
- **Inter-Service Communication**: API patterns, service boundaries
- **Security**: RBAC, permissions, data protection
- **Configuration Management**: Environment variables, settings
- **Logging & Monitoring**: ✅ **UPDATED** - Client-specific logging, error handling

### ⚙️ [ETL Service Guide](./02_etl_service_guide.md)
**Scope**: ETL Service specific functionality and patterns
- **Job Orchestration**: Scheduler, job management, recovery patterns
- **Data Processing**: Jira/Git data extraction, transformation, loading
- **Integration Management**: External API connections, rate limiting
- **Home & Analytics**: Metrics calculation, real-time updates
- **WebSocket Management**: Real-time communication patterns
- **Flow Management**: Status mappings, workflow configurations

### 🔧 [Backend Service Guide](./03_backend_service_guide.md)
**Scope**: Backend Service specific functionality and patterns
- **User Management**: CRUD operations, user lifecycle
- **Session Management**: Login/logout, session validation, termination
- **Permission System**: RBAC implementation, permission checks
- **Authentication APIs**: Token validation, service authentication
- **Admin Statistics**: User metrics, system health
- **Database Operations**: User-related data management

### 🎨 [Frontend App Guide](./04_frontend_app_guide.md)
**Scope**: Frontend application patterns and standards
- **UI/UX Standards**: Design system, component patterns
- **Authentication Flow**: Login/logout, token management
- **State Management**: Session handling, user context
- **Navigation**: Sidebar, routing, page structure
- **Real-time Features**: WebSocket integration, live updates
- **Responsive Design**: Mobile-first, accessibility

## 🎯 Usage Guidelines

### **For AI Assistants:**
1. **Start with Cross-Domain** for platform-wide context
2. **Reference specific guides** for domain-specific work
3. **Follow established patterns** documented in each guide
4. **Update guides** when introducing new patterns or changes

### **For Developers:**
1. **Read relevant guides** before starting work in a domain
2. **Follow documented patterns** for consistency
3. **Update documentation** when patterns evolve
4. **Reference guides** during code reviews

## 🔄 Maintenance

These documents should be updated whenever:
- New architectural patterns are introduced
- Service boundaries change
- Authentication/authorization patterns evolve
- Database schema patterns change
- Frontend standards are updated

## 🎯 Usage Guidelines

### **When to Use Each Guide**
- **Starting new work**: Always begin with Cross-Domain Guide for platform patterns
- **Service-specific tasks**: Use the relevant service guide for detailed implementation
- **Cross-service features**: Reference multiple guides and update Cross-Domain patterns
- **Architecture decisions**: Cross-Domain Guide provides the foundation

### **Recent Updates (2025-07-30)**
- ✅ **Client-Specific Logging**: Complete implementation across all services
- ✅ **Port Corrections**: Frontend now runs on port 3000 (not 5173)
- ✅ **Route Updates**: ETL service uses `/home` (not `/dashboard`)
- ✅ **Job Status Accuracy**: Correct enum values (NOT_STARTED, ERROR, etc.)
- ✅ **Authentication Clarity**: All ETL functionality requires admin credentials

## 📚 Related Documentation

- **Main Guide**: `/docs/AGENT_GUIDANCE.md` (legacy, being migrated)
- **Service READMEs**: Individual service documentation
- **API Documentation**: OpenAPI specs for each service
- **Development Guides**: Setup and development workflows
