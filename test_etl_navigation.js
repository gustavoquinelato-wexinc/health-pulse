// Test script for ETL POST navigation
// Run this in browser console to test the new navigation approach

async function testETLNavigation() {
  console.log('🚀 Testing ETL POST Navigation...');
  
  // Mock token for testing (replace with real token)
  const mockToken = 'test-token-123';
  
  try {
    const ETL_SERVICE_URL = 'http://localhost:8000';
    
    console.log('📤 Sending POST request to ETL service...');
    
    const response = await fetch(`${ETL_SERVICE_URL}/auth/navigate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        token: mockToken,
        return_url: window.location.href
      }),
      credentials: 'include'
    });

    console.log('📥 Response status:', response.status);
    
    if (response.ok) {
      const data = await response.json();
      console.log('✅ Success! Response data:', data);
      
      if (data.redirect_url) {
        console.log(`🔗 Would redirect to: ${ETL_SERVICE_URL}${data.redirect_url}`);
        // Uncomment to actually open the URL
        // window.open(`${ETL_SERVICE_URL}${data.redirect_url}`, '_blank');
      }
    } else {
      console.error('❌ Navigation failed:', response.statusText);
      const errorData = await response.text();
      console.error('Error details:', errorData);
    }
  } catch (error) {
    console.error('💥 Request failed:', error);
  }
}

// Test with real token from localStorage
async function testWithRealToken() {
  const token = localStorage.getItem('pulse_token');
  if (!token) {
    console.error('❌ No token found in localStorage. Please login first.');
    return;
  }
  
  console.log('🔑 Using real token from localStorage');
  console.log('Token preview:', token.substring(0, 20) + '...');
  
  try {
    const ETL_SERVICE_URL = 'http://localhost:8000';
    
    const response = await fetch(`${ETL_SERVICE_URL}/auth/navigate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        token: token,
        return_url: window.location.href
      }),
      credentials: 'include'
    });

    if (response.ok) {
      const data = await response.json();
      console.log('✅ Real token navigation successful!', data);
      
      if (data.redirect_url) {
        console.log(`🚀 Opening ETL service: ${ETL_SERVICE_URL}${data.redirect_url}`);
        window.open(`${ETL_SERVICE_URL}${data.redirect_url}`, '_blank');
      }
    } else {
      console.error('❌ Real token navigation failed:', response.status);
      const errorData = await response.text();
      console.error('Error details:', errorData);
    }
  } catch (error) {
    console.error('💥 Real token request failed:', error);
  }
}

console.log('🧪 ETL Navigation Test Functions Loaded!');
console.log('📋 Available functions:');
console.log('  - testETLNavigation() - Test with mock token');
console.log('  - testWithRealToken() - Test with real token from localStorage');
console.log('');
console.log('💡 Usage: Run testWithRealToken() after logging in to test the complete flow');
