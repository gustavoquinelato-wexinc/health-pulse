#!/usr/bin/env python3
"""
Debug integration configuration and project key parsing
"""

import re
import requests
from app.core.config import get_settings

def debug_integration_parsing():
    """Debug how project keys are being parsed from integration base_search."""
    
    settings = get_settings()
    print("🔍 Debug Integration Project Key Parsing")
    print("=" * 60)
    
    # Test different base_search formats
    test_cases = [
        "PROJECT IN (BDP,BEN,BEX,BST,CDB,CDH,EPE,FG,HBA,HDO,HDS)",
        "project in (BDP,BEN,BEX,BST,CDB,CDH,EPE,FG,HBA,HDO,HDS)",
        "PROJECT IN (BDP, BEN, BEX, BST, CDB, CDH, EPE, FG, HBA, HDO, HDS)",
        'PROJECT IN ("BDP","BEN","BEX","BST","CDB","CDH","EPE","FG","HBA","HDO","HDS")',
        "PROJECT IN ('BDP','BEN','BEX','BST','CDB','CDH','EPE','FG','HBA','HDO','HDS')",
        "",  # Empty case
        None,  # None case
    ]
    
    print("Testing regex parsing with different base_search formats:")
    print()
    
    for i, base_search in enumerate(test_cases, 1):
        print(f"Test {i}: {repr(base_search)}")
        
        project_keys = None
        if base_search:
            # Use the same regex as in jira_extractors.py
            match = re.search(r'PROJECT\s+IN\s*\(([^)]+)\)', base_search, re.IGNORECASE)
            if match:
                project_keys = [key.strip().strip('"\'') for key in match.group(1).split(',')]
        
        print(f"  Result: {project_keys}")
        
        # Test the API call with these project keys
        if project_keys:
            try:
                projects_url = f'{settings.JIRA_URL}/rest/api/3/project/search'
                params = [('maxResults', 5)]
                for project_key in project_keys:
                    params.append(('keys', str(project_key)))
                params.append(('expand', 'issueTypes'))
                
                response = requests.get(projects_url, auth=(settings.JIRA_USERNAME, settings.JIRA_TOKEN), params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    projects = data.get('values', [])
                    print(f"  ✅ API Result: {len(projects)} projects found")
                else:
                    print(f"  ❌ API Error: {response.status_code}")
            except Exception as e:
                print(f"  ❌ API Exception: {e}")
        else:
            print("  ⚠️  No project keys to test")
        
        print()
    
    # Test fallback to environment settings
    print("Testing fallback to environment settings:")
    print(f"Environment JIRA_PROJECTS: {settings.JIRA_PROJECTS}")
    print(f"Parsed project list: {settings.jira_projects_list}")
    
    # Test API call with environment settings
    try:
        projects_url = f'{settings.JIRA_URL}/rest/api/3/project/search'
        params = [('maxResults', 50)]
        for project_key in settings.jira_projects_list:
            params.append(('keys', str(project_key)))
        params.append(('expand', 'issueTypes'))
        
        response = requests.get(projects_url, auth=(settings.JIRA_USERNAME, settings.JIRA_TOKEN), params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            projects = data.get('values', [])
            print(f"✅ Environment settings API result: {len(projects)} projects found")
            for project in projects[:3]:
                key = project.get('key', 'N/A')
                name = project.get('name', 'N/A')
                print(f"  - {key}: {name}")
        else:
            print(f"❌ Environment settings API error: {response.status_code}")
    except Exception as e:
        print(f"❌ Environment settings API exception: {e}")

if __name__ == "__main__":
    debug_integration_parsing()
