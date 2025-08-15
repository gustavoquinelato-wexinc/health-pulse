/**
 * Notification service for showing toast messages and real-time update indicators
 */

export interface Notification {
  id: string
  type: 'success' | 'info' | 'warning' | 'error'
  title: string
  message?: string
  duration?: number
  persistent?: boolean
}

type NotificationListener = (notifications: Notification[]) => void

class NotificationService {
  private notifications: Notification[] = []
  private listeners: NotificationListener[] = []
  private nextId = 1

  /**
   * Add a new notification
   */
  public show(notification: Omit<Notification, 'id'>): string {
    const id = `notification-${this.nextId++}`
    const newNotification: Notification = {
      id,
      duration: 5000, // Default 5 seconds
      ...notification
    }

    this.notifications.push(newNotification)
    this.notifyListeners()

    // Auto-remove after duration (unless persistent)
    if (!newNotification.persistent && newNotification.duration) {
      setTimeout(() => {
        this.remove(id)
      }, newNotification.duration)
    }

    return id
  }

  /**
   * Remove a notification by ID
   */
  public remove(id: string): void {
    this.notifications = this.notifications.filter(n => n.id !== id)
    this.notifyListeners()
  }

  /**
   * Clear all notifications
   */
  public clear(): void {
    this.notifications = []
    this.notifyListeners()
  }

  /**
   * Get all current notifications
   */
  public getAll(): Notification[] {
    return [...this.notifications]
  }

  /**
   * Subscribe to notification changes
   */
  public subscribe(listener: NotificationListener): () => void {
    this.listeners.push(listener)
    
    // Return unsubscribe function
    return () => {
      const index = this.listeners.indexOf(listener)
      if (index > -1) {
        this.listeners.splice(index, 1)
      }
    }
  }

  private notifyListeners(): void {
    this.listeners.forEach(listener => {
      try {
        listener([...this.notifications])
      } catch (error) {
        console.error('Error in notification listener:', error)
      }
    })
  }

  // Convenience methods
  public success(title: string, message?: string, duration?: number): string {
    return this.show({ type: 'success', title, message, duration })
  }

  public info(title: string, message?: string, duration?: number): string {
    return this.show({ type: 'info', title, message, duration })
  }

  public warning(title: string, message?: string, duration?: number): string {
    return this.show({ type: 'warning', title, message, duration })
  }

  public error(title: string, message?: string, duration?: number): string {
    return this.show({ type: 'error', title, message, duration })
  }

  public colorUpdate(message?: string): string {
    return this.show({
      type: 'info',
      title: '🎨 Colors Updated',
      message: message || 'Your color scheme has been updated in real-time',
      duration: 3000
    })
  }
}

// Create singleton instance
const notificationService = new NotificationService()

export default notificationService
export type { NotificationListener }
