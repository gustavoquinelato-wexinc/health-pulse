# 🚨 JIRA API MIGRATION GUIDE - URGENT

## 📅 **Critical Timeline**
- **Deprecation Date**: October 31, 2024 ✅ (Already in effect)
- **Removal Date**: May 1, 2025 ⚠️ (3 months remaining)
- **Status**: MIGRATION IN PROGRESS

## 🔍 **What Changed**

Atlassian deprecated these endpoints:
- ❌ `GET /rest/api/2/search` - Search for issues using JQL (GET)
- ❌ `POST /rest/api/2/search` - Search for issues using JQL (POST)  
- ❌ `POST /rest/api/2/search/id` - Search issue IDs using JQL
- ❌ `POST /rest/api/2/expression/eval` - Evaluate Jira expression

## ✅ **New Replacement Endpoints**

| Old Endpoint | New Endpoint | Status |
|--------------|--------------|---------|
| `GET/POST /rest/api/2/search` | `POST /rest/api/3/search/jql` | ✅ UPDATED |
| `POST /rest/api/2/search/id` | `POST /rest/api/3/search/jql` | ✅ UPDATED |
| `POST /rest/api/2/expression/eval` | `POST /rest/api/3/expression/evaluate` | ⚠️ TODO |

## 🔧 **Key Changes Made**

### 1. **Updated `jira_client.py`** ✅
- **Method**: `get_issues()` 
- **Change**: Uses `POST /rest/api/3/search/jql` instead of `GET /rest/api/2/search`
- **Pagination**: Token-based (`nextPageToken`) instead of offset-based (`startAt`)
- **Request**: Now uses POST with JSON body instead of GET with query params

### 2. **Updated `jira_job.py`** ✅  
- **Method**: `custom_get_issues()`
- **Change**: Uses new enhanced JQL API
- **Fields**: Properly formatted as array instead of comma-separated string

### 3. **Added New Methods** ✅
- **Method**: `get_issue_count_approximate()`
- **Purpose**: Get issue counts using `/rest/api/3/search/approximate-count`

## 🚨 **Breaking Changes to Handle**

### 1. **No Total Count Available**
- **Old**: API returned `total` count immediately
- **New**: No total count provided, use approximate count API if needed
- **Impact**: Progress indicators show "batch progress" instead of percentage

### 2. **Token-Based Pagination**
- **Old**: `startAt` + `maxResults` for pagination
- **New**: `nextPageToken` for continuation
- **Impact**: Can't jump to arbitrary pages, must paginate sequentially

### 3. **Field Requests Required**
- **Old**: All fields returned by default
- **New**: Only IDs returned unless explicitly requested via `fields` parameter
- **Impact**: Must specify `fields: ['*all']` to get all data

### 4. **Limited Comments/Changelogs**
- **Old**: All comments and changelogs included
- **New**: Max 20 comments, 40 changelog items
- **Impact**: Use separate APIs for more data if needed

## 🔄 **Migration Status**

### ✅ **Completed**
- [x] Updated main JQL search endpoint
- [x] Fixed pagination logic
- [x] Updated custom query functionality  
- [x] Added approximate count method
- [x] Updated changelog endpoint to v3

### ⚠️ **Still TODO**
- [ ] Test with real Jira instance
- [ ] Update expression evaluation (if used)
- [ ] Add bulk fetch for large datasets
- [ ] Implement search-and-reconcile pattern for consistency
- [ ] Update error handling for new response formats

## 🧪 **Testing Required**

1. **Basic JQL Search**: Test with simple queries
2. **Pagination**: Test with large result sets (>100 issues)
3. **Custom Queries**: Test custom JQL functionality
4. **Error Handling**: Test with invalid JQL
5. **Performance**: Compare speed with old API

## 📋 **Recommended Next Steps**

1. **Immediate**: Test current changes in development
2. **Short-term**: Add comprehensive error handling
3. **Medium-term**: Implement bulk fetch patterns for performance
4. **Long-term**: Consider caching strategies for better performance

## 🔗 **References**

- [Atlassian Migration Guide](https://developer.atlassian.com/changelog/#CHANGE-2046)
- [Enhanced JQL API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/)
- [Migration Blog Post](https://developer.atlassian.com/blog/2024/avoiding-pitfalls-guide-smooth-migration-enhanced-jql-apis/)

## ⚡ **Quick Test Commands**

```bash
# Test the migration
cd services/etl-service
python -m pytest tests/ -k jira -v

# Run a quick Jira sync to test
# (Use the ETL service admin panel)
```

---
**⚠️ CRITICAL**: This migration must be completed before May 1, 2025, or Jira integration will break!
