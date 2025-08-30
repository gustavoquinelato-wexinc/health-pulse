#!/usr/bin/env python3
"""
Test Jira API connection and project fetching
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_jira_connection():
    """Test basic Jira API connection and project fetching."""
    
    # Get credentials from environment
    jira_url = os.getenv('JIRA_URL')
    jira_username = os.getenv('JIRA_USERNAME')
    jira_token = os.getenv('JIRA_TOKEN')
    jira_projects = os.getenv('JIRA_PROJECTS', '').split(',')
    
    print("🔍 Testing Jira API Connection")
    print("=" * 50)
    print(f"JIRA_URL: {jira_url}")
    print(f"JIRA_USERNAME: {jira_username}")
    print(f"JIRA_TOKEN: {jira_token[:10]}...{jira_token[-4:] if jira_token else 'None'}")
    print(f"JIRA_PROJECTS: {jira_projects}")
    print()
    
    if not all([jira_url, jira_username, jira_token]):
        print("❌ Missing required environment variables")
        return False
    
    # Test 1: Basic authentication
    print("1️⃣ Testing basic authentication...")
    try:
        auth_url = f"{jira_url}/rest/api/3/myself"
        response = requests.get(auth_url, auth=(jira_username, jira_token), timeout=10)
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            user_info = response.json()
            print(f"   ✅ Authenticated as: {user_info.get('displayName', 'Unknown')}")
            print(f"   Account ID: {user_info.get('accountId', 'Unknown')}")
        else:
            print(f"   ❌ Authentication failed: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False
    
    print()
    
    # Test 2: Fetch all accessible projects (no filter)
    print("2️⃣ Testing project access (no filter)...")
    try:
        projects_url = f"{jira_url}/rest/api/3/project/search"
        params = {'maxResults': 10}
        
        response = requests.get(projects_url, auth=(jira_username, jira_token), params=params, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            projects = data.get('values', [])
            total = data.get('total', 0)
            
            print(f"   ✅ Found {len(projects)} projects (total: {total})")
            for project in projects[:5]:
                print(f"      - {project.get('key', 'N/A')}: {project.get('name', 'N/A')}")
            if len(projects) > 5:
                print(f"      ... and {len(projects) - 5} more")
        else:
            print(f"   ❌ Failed to fetch projects: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Error fetching projects: {e}")
        return False
    
    print()
    
    # Test 3: Fetch projects with filter
    print("3️⃣ Testing project access (with filter)...")
    try:
        projects_url = f"{jira_url}/rest/api/3/project/search"
        
        # Build params with project keys
        params = [('maxResults', 50)]
        for project_key in jira_projects:
            if project_key.strip():
                params.append(('keys', project_key.strip()))
        
        print(f"   Filtering by projects: {[p.strip() for p in jira_projects if p.strip()]}")
        
        response = requests.get(projects_url, auth=(jira_username, jira_token), params=params, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            projects = data.get('values', [])
            total = data.get('total', 0)
            
            print(f"   ✅ Found {len(projects)} filtered projects (total: {total})")
            for project in projects:
                print(f"      - {project.get('key', 'N/A')}: {project.get('name', 'N/A')}")
                
            if len(projects) == 0:
                print("   ⚠️  No projects found with the specified filter!")
                print("   This could mean:")
                print("      - The project keys don't exist")
                print("      - You don't have permission to access these projects")
                print("      - The project keys are incorrect")
        else:
            print(f"   ❌ Failed to fetch filtered projects: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Error fetching filtered projects: {e}")
        return False
    
    print()
    print("✅ Jira API connection test completed!")
    return True

if __name__ == "__main__":
    test_jira_connection()
