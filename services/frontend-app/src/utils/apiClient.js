/**
 * API Client with client-aware logging.
 * Wraps fetch calls with automatic logging and error handling.
 */

import clientLogger from './clientLogger';

class ApiClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
    }
    
    /**
     * Get authentication token
     */
    getAuthToken() {
        // Check localStorage first
        let token = localStorage.getItem('pulse_token');
        
        // Fallback to cookies
        if (!token) {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'pulse_token') {
                    token = value;
                    break;
                }
            }
        }
        
        return token;
    }
    
    /**
     * Prepare headers with authentication
     */
    prepareHeaders(customHeaders = {}) {
        const headers = { ...this.defaultHeaders, ...customHeaders };
        
        const token = this.getAuthToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }
        
        return headers;
    }
    
    /**
     * Core API call method with logging
     */
    async apiCall(method, url, options = {}) {
        const startTime = performance.now();
        const fullUrl = `${this.baseURL}${url}`;
        
        // Prepare request
        const requestOptions = {
            method: method.toUpperCase(),
            headers: this.prepareHeaders(options.headers),
            ...options
        };
        
        // Log request start
        clientLogger.info(`API ${method.toUpperCase()} ${url} started`, {
            type: 'api_request',
            method: method.toUpperCase(),
            url: fullUrl,
            hasBody: !!options.body
        });
        
        try {
            const response = await fetch(fullUrl, requestOptions);
            const duration = performance.now() - startTime;
            
            // Log response
            clientLogger.logApiCall(
                method.toUpperCase(),
                url,
                response.status,
                Math.round(duration)
            );
            
            // Handle different response types
            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { message: response.statusText };
                }
                
                const error = new Error(errorData.message || `HTTP ${response.status}`);
                error.status = response.status;
                error.data = errorData;
                
                throw error;
            }
            
            // Return response for further processing
            return response;
            
        } catch (error) {
            const duration = performance.now() - startTime;
            
            // Log error
            clientLogger.logApiCall(
                method.toUpperCase(),
                url,
                error.status || 0,
                Math.round(duration),
                error
            );
            
            throw error;
        }
    }
    
    /**
     * GET request
     */
    async get(url, options = {}) {
        const response = await this.apiCall('GET', url, options);
        return response.json();
    }
    
    /**
     * POST request
     */
    async post(url, data = null, options = {}) {
        const requestOptions = {
            ...options,
            body: data ? JSON.stringify(data) : undefined
        };
        
        const response = await this.apiCall('POST', url, requestOptions);
        return response.json();
    }
    
    /**
     * PUT request
     */
    async put(url, data = null, options = {}) {
        const requestOptions = {
            ...options,
            body: data ? JSON.stringify(data) : undefined
        };
        
        const response = await this.apiCall('PUT', url, requestOptions);
        return response.json();
    }
    
    /**
     * DELETE request
     */
    async delete(url, options = {}) {
        const response = await this.apiCall('DELETE', url, options);
        
        // Handle empty responses
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        }
        
        return { success: true };
    }
    
    /**
     * Download file with proper error handling
     */
    async downloadFile(url, filename = null, options = {}) {
        try {
            const response = await this.apiCall('GET', url, options);
            
            if (!response.ok) {
                throw new Error(`Download failed: ${response.statusText}`);
            }
            
            const blob = await response.blob();
            
            // Extract filename from response headers if not provided
            if (!filename) {
                const contentDisposition = response.headers.get('content-disposition');
                if (contentDisposition) {
                    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                    if (filenameMatch) {
                        filename = filenameMatch[1];
                    }
                }
            }
            
            // Create download link
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = filename || 'download';
            link.style.display = 'none';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Clean up
            window.URL.revokeObjectURL(downloadUrl);
            
            clientLogger.info(`File downloaded: ${filename}`, {
                type: 'file_download',
                filename,
                size: blob.size
            });
            
            return { success: true, filename, size: blob.size };
            
        } catch (error) {
            clientLogger.error(`File download failed: ${url}`, {
                type: 'file_download_error',
                url,
                error: error.message
            });
            
            throw error;
        }
    }
    
    /**
     * Upload file with progress tracking
     */
    async uploadFile(url, file, options = {}) {
        const startTime = performance.now();
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            // Add any additional form data
            if (options.data) {
                Object.keys(options.data).forEach(key => {
                    formData.append(key, options.data[key]);
                });
            }
            
            const requestOptions = {
                method: 'POST',
                headers: this.prepareHeaders({ 
                    // Remove Content-Type to let browser set it with boundary
                    'Content-Type': undefined,
                    ...options.headers 
                }),
                body: formData
            };
            
            const response = await fetch(`${this.baseURL}${url}`, requestOptions);
            const duration = performance.now() - startTime;
            
            clientLogger.info(`File upload completed: ${file.name}`, {
                type: 'file_upload',
                filename: file.name,
                size: file.size,
                duration: Math.round(duration),
                status: response.status
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: response.statusText }));
                throw new Error(errorData.message || `Upload failed: ${response.statusText}`);
            }
            
            return response.json();
            
        } catch (error) {
            const duration = performance.now() - startTime;
            
            clientLogger.error(`File upload failed: ${file.name}`, {
                type: 'file_upload_error',
                filename: file.name,
                size: file.size,
                duration: Math.round(duration),
                error: error.message
            });
            
            throw error;
        }
    }
}

// Create singleton instance
const apiClient = new ApiClient();

export default apiClient;
