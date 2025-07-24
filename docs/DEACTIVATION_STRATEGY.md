# Deactivation Strategy and Metrics Exclusion Guide

## 📋 **Overview**

This document defines the comprehensive strategy for handling record deactivation in the Pulse Platform, including the critical metrics exclusion rules that ensure data integrity and accurate analytics.

## 🎯 **Core Philosophy**

### **Deactivation vs Deletion**
- **Deactivate**: Set `active = False` to preserve referential integrity while excluding from active operations
- **Delete**: Physical removal only when no dependencies exist and data is truly unwanted
- **Principle**: Deactivation is preferred to maintain audit trails and prevent orphaned data

### **Metrics Exclusion Rule**
> **CRITICAL**: All metrics calculations must exclude data connected to deactivated records at ANY level of the relationship chain.

## 🏗️ **Relationship Chain Impact**

### **Flow Step Deactivation Impact**
```
Deactivated Flow Step
    ↓ (excludes)
Status Mappings → Statuses → Issues → All Related Data
```

When a Flow Step is deactivated:
- ❌ Exclude all Status Mappings pointing to it
- ❌ Exclude all Statuses using those Status Mappings  
- ❌ Exclude all Issues with those Statuses
- ❌ Exclude all related data (changelogs, PR links, etc.)

### **Status Mapping Deactivation Impact**
```
Deactivated Status Mapping
    ↓ (excludes)
Statuses → Issues → All Related Data
```

### **Issue Type Hierarchy Deactivation Impact**
```
Deactivated Issue Type Hierarchy
    ↓ (excludes)
Issue Type Mappings → Issue Types → Issues → All Related Data
```

## 📊 **Metrics Implementation Rules**

### **Standard Metrics Queries**
```sql
-- ❌ WRONG: Only checks direct table
SELECT COUNT(*) FROM issues WHERE active = TRUE;

-- ✅ CORRECT: Checks entire relationship chain
SELECT COUNT(*) 
FROM issues i
JOIN statuses s ON i.status_id = s.id
JOIN status_mappings sm ON s.status_mapping_id = sm.id  
JOIN flow_steps fs ON sm.flow_step_id = fs.id
WHERE i.active = TRUE 
  AND s.active = TRUE 
  AND sm.active = TRUE 
  AND fs.active = TRUE;
```

### **Workflow Metrics Example**
```sql
-- Issues by Flow Step (excluding deactivated chain)
SELECT 
    fs.name as flow_step,
    COUNT(i.id) as issue_count
FROM flow_steps fs
JOIN status_mappings sm ON fs.id = sm.flow_step_id
JOIN statuses s ON sm.id = s.status_mapping_id
JOIN issues i ON s.id = i.status_id
WHERE fs.active = TRUE 
  AND sm.active = TRUE 
  AND s.active = TRUE 
  AND i.active = TRUE
GROUP BY fs.id, fs.name
ORDER BY fs.step_number;
```

### **Issue Type Metrics Example**
```sql
-- Issues by Issue Type (excluding deactivated chain)
SELECT 
    ih.level_name,
    COUNT(i.id) as issue_count
FROM issuetype_hierarchies ih
JOIN issuetype_mappings im ON ih.id = im.issuetype_hierarchy_id
JOIN issuetypes it ON im.id = it.issuetype_mapping_id
JOIN issues i ON it.id = i.issuetype_id
WHERE ih.active = TRUE 
  AND im.active = TRUE 
  AND it.active = TRUE 
  AND i.active = TRUE
GROUP BY ih.id, ih.level_name
ORDER BY ih.level_number;
```

## 🎨 **User Experience Strategy**

### **Deactivation Modal Options**

#### **1. Keep Mappings Active (Not Recommended)**
- Dependencies remain active but point to inactive parent
- **Impact**: New extractions still map to deactivated records
- **Metrics**: Data appears in "data quality" reports but excluded from standard metrics
- **Use Case**: Temporary deactivation with planned reactivation

#### **2. Reassign Dependencies (Recommended)**
- Move all dependencies to another active record
- **Impact**: Seamless transition, no data gaps
- **Metrics**: All data remains in standard metrics under new classification
- **Use Case**: Workflow reorganization, consolidation

#### **3. Cascade Deactivation**
- Deactivate the record and all its dependencies
- **Impact**: Entire data chain excluded from metrics
- **Metrics**: Large portions of historical data excluded
- **Use Case**: Deprecated workflows, data cleanup

## 🔧 **Implementation Guidelines**

### **For Metrics Development**
1. **Always use relationship joins** to check active status at all levels
2. **Create helper functions** for common active-only filtering
3. **Provide toggle options** for including/excluding inactive data
4. **Document exclusion impact** in metric descriptions

### **For API Development**
1. **Default to active-only** in all list endpoints
2. **Provide include_inactive parameter** for admin/debugging use
3. **Clear documentation** about what data is included/excluded
4. **Consistent filtering** across all related endpoints

### **For Admin Interface**
1. **Visual indicators** for inactive records (grayed out, badges)
2. **Dependency warnings** before deactivation
3. **Impact preview** showing what will be excluded from metrics
4. **Bulk operations** with clear scope indication

## 📈 **Metrics Dashboard Strategy**

### **Standard Dashboards**
- **Default View**: Active records only
- **Clean Metrics**: Exclude all deactivated relationship chains
- **Performance Focus**: Optimized for current operational data

### **Data Quality Dashboards**
- **Include Inactive**: Toggle to show deactivated records
- **Orphaned Data**: Identify records pointing to inactive parents
- **Coverage Analysis**: Show gaps in active configuration
- **Migration Planning**: Assist in cleanup and reorganization

### **Administrative Reports**
- **Deactivation Impact**: Show what data would be excluded
- **Dependency Analysis**: Visualize relationship chains
- **Historical Trends**: Compare metrics before/after deactivations
- **Data Completeness**: Track active vs total data ratios

## ⚠️ **Critical Considerations**

### **Data Extraction Behavior**
- **New Jira/GitHub data** may still map to deactivated records if no reassignment occurred
- **Monitor extraction logs** for mappings to inactive records
- **Regular cleanup** of orphaned mappings recommended

### **Historical Data Impact**
- **Deactivation affects historical metrics** retroactively
- **Consider data archival** before major deactivations
- **Document business impact** of excluding historical data

### **Performance Implications**
- **Complex joins required** for proper active-only filtering
- **Index optimization** needed for relationship chain queries
- **Query performance monitoring** essential for large datasets

## 🎯 **Best Practices Summary**

### **For Developers**
1. **Always filter by active status** at all relationship levels
2. **Use consistent helper functions** for active-only queries
3. **Test metrics impact** before implementing deactivation features
4. **Document exclusion rules** in code comments

### **For Administrators**
1. **Plan deactivations carefully** considering metrics impact
2. **Use reassignment strategy** when possible to preserve data continuity
3. **Monitor data quality reports** after deactivations
4. **Communicate changes** to metrics consumers

### **For Users**
1. **Understand metrics exclusion** when deactivating records
2. **Choose appropriate strategy** based on business needs
3. **Review impact warnings** in deactivation modals
4. **Use data quality views** to verify deactivation effects

## 📚 **Related Documentation**

- [Agent Guidance](AGENT_GUIDANCE.md) - Development guidelines including deactivation rules
- [GitHub Job Guide](GITHUB_JOB_GUIDE.md) - ETL job recovery and data extraction
- [Architecture](ARCHITECTURE.md) - System architecture and data flow
