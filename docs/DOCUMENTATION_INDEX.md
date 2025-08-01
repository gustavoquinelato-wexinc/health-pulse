# Pulse Platform Documentation Index

This directory contains comprehensive documentation for the Pulse Platform, covering cross-service architecture, systems, and processes.

## 📚 Documentation Structure

### **Platform-Level Documentation** (This Directory)
```
docs/
├── DOCUMENTATION_INDEX.md       # This index (you are here)
├── SECURITY_AUDIT_COMPLETE.md   # 🔒 Security audit certification (PRODUCTION-READY)
├── ENVIRONMENT_SETUP.md         # Service-specific environment configuration
├── MULTI_INSTANCE_SETUP.md      # Multi-client ETL deployment guide
├── AGENT_GUIDANCE.md            # Guidance for Augment Code agents
├── ARCHITECTURE.md              # System architecture and design
├── COLOR_SYSTEM.md              # 5-color schema system and theming guide
├── MIGRATION_GUIDE.md           # Database migration system
├── SCRIPTS_GUIDE.md             # Cross-service scripts and utilities
├── GITHUB_JOB_GUIDE.md          # GitHub ETL job checkpoint and recovery system
├── DEACTIVATION_STRATEGY.md     # Record deactivation and metrics exclusion strategy
├── ADMIN_PAGE_TEMPLATE.md       # Template and guidelines for creating new admin pages
├── CLIENT_LOGGING_QUICK_START.md # ⭐ Quick start guide for client-specific logging
├── CLIENT_SPECIFIC_LOGGING.md   # Comprehensive client-specific logging implementation
└── DEPLOYMENT.md                # Deployment and infrastructure
```

### **Service-Specific Documentation**
```
services/
├── etl-service/
│   ├── README.md             # ETL service overview and features
│   └── docs/
│       ├── DEVELOPMENT_GUIDE.md  # Development, testing, debugging
│       └── LOG_MANAGEMENT.md     # Logging system details
├── frontend-app/
│   └── README.md             # Frontend application guide
└── backend-api/
    └── README.md             # Backend API guide (when created)
```

## 🎯 Quick Navigation

### **Getting Started**
- **[Main README](../README.md)** - Platform overview and quick start
- **[🤖 Agent Guidance](AGENT_GUIDANCE.md)** - Essential guidance for Augment Code agents
- **[Architecture](ARCHITECTURE.md)** - Understand the system design
- **[Deployment](DEPLOYMENT.md)** - Set up and deploy the platform

### **Development**
- **[ETL Development](../services/etl-service/docs/DEVELOPMENT_GUIDE.md)** - ETL service development workflow
- **[Color System](COLOR_SYSTEM.md)** - 5-color schema system and theming guide
- **[Scripts Guide](SCRIPTS_GUIDE.md)** - Cross-service scripts and utilities
- **[Migration Guide](MIGRATION_GUIDE.md)** - Database schema management

### **Operations**
- **[ETL Service](../services/etl-service/README.md)** - ETL service features and operations
- **[GitHub Job Guide](GITHUB_JOB_GUIDE.md)** - GitHub ETL job checkpoint system and recovery procedures
- **[Deactivation Strategy](DEACTIVATION_STRATEGY.md)** - Record deactivation and metrics exclusion strategy
- **[Admin Page Template](ADMIN_PAGE_TEMPLATE.md)** - Template and guidelines for creating new admin pages
- **[Log Management](../services/etl-service/docs/LOG_MANAGEMENT.md)** - Logging and monitoring

## 📖 Documentation Guidelines

### **Platform vs Service Documentation**

**Platform Documentation** (`/docs`) covers:
- ✅ Cross-service architecture and design
- ✅ System-wide processes and workflows
- ✅ Shared utilities and scripts
- ✅ Deployment and infrastructure
- ✅ Migration and database management

**Service Documentation** (`/services/[service]/docs/`) covers:
- ✅ Service-specific development guides
- ✅ Service configuration and setup
- ✅ Service-specific testing and debugging
- ✅ Service API documentation
- ✅ Service-specific troubleshooting

### **Documentation Standards**

1. **Clear Structure**: Use consistent headings and organization
2. **Practical Examples**: Include working code examples and commands
3. **Current Information**: Keep documentation up-to-date with code changes
4. **Cross-References**: Link to related documentation appropriately
5. **User-Focused**: Write for the intended audience (developers, operators, etc.)

### **File Naming Conventions**

- **README.md**: Overview and quick start for the directory/service
- **[TOPIC]_GUIDE.md**: Comprehensive guides (e.g., DEVELOPMENT_GUIDE.md)
- **[SYSTEM].md**: System-specific documentation (e.g., ARCHITECTURE.md)
- **ALL_CAPS**: For major documentation files
- **lowercase**: For specific feature documentation

## 🔄 Maintenance

### **Updating Documentation**

1. **Code Changes**: Update relevant documentation when making code changes
2. **New Features**: Create or update guides for new functionality
3. **Deprecations**: Mark deprecated features and provide migration paths
4. **Reviews**: Include documentation updates in code reviews

### **Documentation Ownership**

- **Platform Docs**: Maintained by platform team
- **Service Docs**: Maintained by service owners
- **Cross-References**: Coordinate updates across teams

## 🎯 Contributing

When adding new documentation:

1. **Choose the Right Location**:
   - Platform-wide topics → `/docs`
   - Service-specific topics → `/services/[service]/docs/`

2. **Follow Naming Conventions**:
   - Use descriptive, consistent names
   - Follow the established patterns

3. **Update Cross-References**:
   - Add links from related documentation
   - Update this index if needed

4. **Test Examples**:
   - Verify all code examples work
   - Test all commands and procedures

### **Testing Documentation**
```
tests/
├── README.md                 # Test overview and running instructions
├── test_client_isolation_security.py  # 🚨 CRITICAL security validation
├── test_client_name_lookup.py         # Client name lookup functionality
└── test_per_client_orchestrators.py   # Multi-instance architecture validation
```

## 📋 Documentation Checklist

When creating or updating documentation:

- [ ] Clear purpose and audience defined
- [ ] Consistent structure and formatting
- [ ] Working examples and commands
- [ ] Cross-references to related docs
- [ ] Updated index/navigation
- [ ] Reviewed for accuracy
- [ ] Tested procedures and examples

---

**For the complete platform overview, see:** [Main README](../README.md)
