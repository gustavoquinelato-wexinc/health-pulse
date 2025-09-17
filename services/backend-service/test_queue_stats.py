# Test the fixed queue stats endpoint
import requests
import json

try:
    # Test health endpoint first
    health_response = requests.get('http://localhost:3002/api/v1/health')
    print(f'Health check: {health_response.status_code}')
    
    if health_response.status_code == 200:
        print('✅ Backend is running on port 3002')
        
        # Try to get admin token
        login_response = requests.post('http://localhost:3002/auth/login', json={
            'email': 'admin@pulse.com',
            'password': 'admin123'
        })
        
        if login_response.status_code == 200:
            token = login_response.json()['access_token']
            headers = {'Authorization': f'Bearer {token}'}
            
            # Test queue stats endpoint
            stats_response = requests.get('http://localhost:3002/api/v1/vectorization/queue-stats', headers=headers)
            print(f'Queue stats response: {stats_response.status_code}')
            
            if stats_response.status_code == 200:
                print('✅ Queue stats endpoint working!')
                print(json.dumps(stats_response.json(), indent=2))
            else:
                print(f'❌ Queue stats failed: {stats_response.text}')
        else:
            print(f'❌ Admin login failed: {login_response.status_code} - {login_response.text}')
    else:
        print('❌ Backend not responding on port 3002')
        
except Exception as e:
    print(f'Error: {e}')
