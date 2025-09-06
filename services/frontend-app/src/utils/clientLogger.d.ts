/**
 * TypeScript declarations for clientLogger.js
 */

interface LogData {
  [key: string]: any;
}

interface TenantLogger {
  clientName: string | null;
  clientId: number | null;
  userId: number | null;
  initialized: boolean;

  // Core logging methods
  log(level: string, message: string, data?: LogData): void;
  debug(message: string, data?: LogData): void;
  info(message: string, data?: LogData): void;
  warn(message: string, data?: LogData): void;
  error(message: string, data?: LogData): void;

  // Specialized logging methods
  logApiCall(method: string, url: string, status: number, duration: number, error?: Error | null): void;
  logUserAction(action: string, element: string, data?: LogData): void;
  logNavigation(from: string, to: string): void;

  // Utility methods
  updateTenantContext(): void;
  flushLogs(): Promise<void>;
}

declare const clientLogger: TenantLogger;
export default clientLogger;
