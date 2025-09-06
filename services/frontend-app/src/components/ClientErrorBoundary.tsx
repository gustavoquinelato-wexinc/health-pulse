/**
 * Tenant-aware Error Boundary component.
 * Catches React errors and logs them with client context.
 * Updated to TypeScript for better type safety.
 */

import React, { ReactNode } from 'react';
import clientLogger from '../utils/clientLogger';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: React.ErrorInfo | null;
}

class TenantErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        // Update state so the next render will show the fallback UI
        return { hasError: true };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        // Log the error with client context
        this.setState({
            error,
            errorInfo
        });

        // Log to client logger with structured data
        clientLogger.error('React Error Boundary caught error', {
            timestamp: new Date().toISOString(),
            level: 'ERROR',
            client: clientLogger.clientName,
            clientId: clientLogger.clientId,
            userId: clientLogger.userId,
            error: {
                name: error.name,
                message: error.message,
                stack: error.stack
            },
            errorInfo: {
                componentStack: errorInfo.componentStack
            },
            url: window.location.href,
            userAgent: navigator.userAgent
        });

        // Also log to console for development
        console.error('React Error Boundary caught error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            // Fallback UI
            return (
                <div style={{
                    padding: '20px',
                    margin: '20px',
                    border: '1px solid #ff6b6b',
                    borderRadius: '8px',
                    backgroundColor: '#ffe0e0',
                    color: '#d63031',
                    fontFamily: 'Arial, sans-serif'
                }}>
                    <h2 style={{ margin: '0 0 10px 0', fontSize: '18px' }}>
                        🚨 Something went wrong
                    </h2>
                    <p style={{ margin: '0 0 15px 0', fontSize: '14px' }}>
                        An unexpected error occurred. The error has been logged and our team has been notified.
                    </p>
                    <details style={{ fontSize: '12px', marginTop: '10px' }}>
                        <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                            Technical Details (Click to expand)
                        </summary>
                        <div style={{
                            marginTop: '10px',
                            padding: '10px',
                            backgroundColor: '#f8f8f8',
                            border: '1px solid #ddd',
                            borderRadius: '4px',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            whiteSpace: 'pre-wrap',
                            overflow: 'auto',
                            maxHeight: '200px'
                        }}>
                            <strong>Error:</strong> {this.state.error?.toString()}<br />
                            <strong>Component Stack:</strong> {this.state.errorInfo?.componentStack}
                        </div>
                    </details>
                    <div style={{ marginTop: '15px' }}>
                        <button
                            onClick={() => window.location.reload()}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: '#0984e3',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '14px',
                                marginRight: '10px'
                            }}
                        >
                            🔄 Reload Page
                        </button>
                        <button
                            onClick={() => window.history.back()}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: '#636e72',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '14px'
                            }}
                        >
                            ← Go Back
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default TenantErrorBoundary;
