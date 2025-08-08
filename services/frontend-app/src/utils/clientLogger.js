/**
 * Client-aware logging utility for Frontend Application.
 * Provides client-specific logging with optional backend transmission.
 */

class ClientLogger {
    constructor() {
        this.clientName = null;
        this.clientId = null;
        this.userId = null;
        this.initialized = false;
        this.logBuffer = [];
        this.maxBufferSize = 100;

        // Initialize client context
        this.initializeClientContext();
    }

    /**
     * Initialize client context from authentication token
     */
    initializeClientContext() {
        try {
            const token = this.getAuthToken();
            if (token) {
                const payload = JSON.parse(atob(token.split('.')[1]));
                // Use client_id as client name since client_name is not in JWT
                this.clientName = payload.client_id ? `client_${payload.client_id}` : 'unknown';
                this.clientId = payload.client_id || null;
                this.userId = payload.user_id || null;
                this.initialized = true;
            } else {
                this.clientName = 'anonymous';
                this.clientId = null;
                this.userId = null;
                this.initialized = false;
            }
        } catch (error) {
            this.clientName = 'error';
            this.clientId = null;
            this.userId = null;
            this.initialized = false;
            console.error('Failed to initialize client logger:', error);
        }
    }

    /**
     * Get authentication token from localStorage or cookies
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
     * Core logging method
     */
    log(level, message, data = {}) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level: level.toUpperCase(),
            client: this.clientName,
            clientId: this.clientId,
            userId: this.userId,
            message,
            url: window.location.href,
            userAgent: navigator.userAgent,
            ...data
        };

        // Console logging with client prefix
        const clientPrefix = `[${this.clientName.toUpperCase()}]`;
        const consoleMethod = console[level] || console.log;

        if (data && Object.keys(data).length > 0) {
            consoleMethod(clientPrefix, message, logEntry);
        } else {
            consoleMethod(clientPrefix, message);
        }

        // Add to buffer for potential backend transmission
        this.addToBuffer(logEntry);

        // Optional: Send critical errors immediately to backend
        if (level === 'error') {
            this.sendToBackend(logEntry);
        }
    }

    /**
     * Add log entry to buffer
     */
    addToBuffer(logEntry) {
        this.logBuffer.push(logEntry);

        // Maintain buffer size
        if (this.logBuffer.length > this.maxBufferSize) {
            this.logBuffer.shift(); // Remove oldest entry
        }
    }

    /**
     * Get backend URL for API calls
     */
    getBackendUrl() {
        // Use environment variable or default to localhost:3001
        return import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001';
    }

    /**
     * Send log entry to backend service
     */
    async sendToBackend(logEntry) {
        try {
            const token = this.getAuthToken();
            if (!token) return; // Can't send without authentication

            await fetch(`${this.getBackendUrl()}/api/v1/logs/frontend`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(logEntry)
            });
        } catch (error) {
            // Don't log this error to avoid infinite loops
            console.warn('Failed to send log to backend:', error);
        }
    }

    /**
     * Flush all buffered logs to backend
     */
    async flushLogs() {
        if (this.logBuffer.length === 0) return;

        try {
            const token = this.getAuthToken();
            if (!token) return;

            await fetch(`${this.getBackendUrl()}/api/v1/logs/frontend/batch`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    logs: [...this.logBuffer]
                })
            });

            // Clear buffer after successful transmission
            this.logBuffer = [];
        } catch (error) {
            console.warn('Failed to flush logs to backend:', error);
        }
    }

    /**
     * Convenience methods for different log levels
     */
    debug(message, data) { this.log('debug', message, data); }
    info(message, data) { this.log('info', message, data); }
    warn(message, data) { this.log('warn', message, data); }
    error(message, data) { this.log('error', message, data); }

    /**
     * Log API calls
     */
    logApiCall(method, url, status, duration, error = null) {
        const logData = {
            type: 'api_call',
            method,
            url,
            status,
            duration,
            error: error ? error.message : null
        };

        if (error || status >= 400) {
            this.error(`API ${method} ${url} failed`, logData);
        } else {
            this.info(`API ${method} ${url} completed`, logData);
        }
    }

    /**
     * Log user interactions
     */
    logUserAction(action, element, data = {}) {
        this.info(`User action: ${action}`, {
            type: 'user_action',
            action,
            element,
            ...data
        });
    }

    /**
     * Log navigation events
     */
    logNavigation(from, to) {
        this.info('Navigation', {
            type: 'navigation',
            from,
            to
        });
    }

    /**
     * Update client context (call when user logs in/out)
     */
    updateClientContext() {
        this.initializeClientContext();
    }
}

// Create singleton instance
const clientLogger = new ClientLogger();

// Auto-flush logs periodically
setInterval(() => {
    clientLogger.flushLogs();
}, 30000); // Flush every 30 seconds

// Flush logs before page unload
window.addEventListener('beforeunload', () => {
    clientLogger.flushLogs();
});

export default clientLogger;
