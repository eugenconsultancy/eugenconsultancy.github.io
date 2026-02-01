// static/js/notifications_websocket.js
class NotificationWebSocket {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000; // 3 seconds
        this.pingInterval = null;
        this.eventHandlers = {
            'notification': this.handleNotification.bind(this),
            'order_update': this.handleOrderUpdate.bind(this),
            'new_message': this.handleNewMessage.bind(this),
            'payment_update': this.handlePaymentUpdate.bind(this),
            'system_alert': this.handleSystemAlert.bind(this),
            'unread_count_update': this.handleUnreadCountUpdate.bind(this),
            'notification_read': this.handleNotificationRead.bind(this),
            'initial_data': this.handleInitialData.bind(this),
            'preferences_updated': this.handlePreferencesUpdated.bind(this),
            'pong': this.handlePong.bind(this),
            'subscribed': this.handleSubscribed.bind(this),
            'unsubscribed': this.handleUnsubscribed.bind(this)
        };
    }

    connect() {
        // Determine WebSocket protocol
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = this.handleOpen.bind(this);
            this.socket.onmessage = this.handleMessage.bind(this);
            this.socket.onclose = this.handleClose.bind(this);
            this.socket.onerror = this.handleError.bind(this);
            
        } catch (error) {
            console.error('Error creating WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }

    handleOpen(event) {
        console.log('Notification WebSocket connected');
        this.reconnectAttempts = 0;
        
        // Start ping interval to keep connection alive
        this.startPingInterval();
        
        // Request initial unread count
        this.getUnreadCount();
        
        // Subscribe to notification categories based on user preferences
        this.subscribeToCategories(['order_updates', 'messages', 'payments', 'system']);
        
        // Dispatch custom event for connection established
        this.dispatchEvent('websocket_connected', { timestamp: new Date().toISOString() });
    }

    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            const handler = this.eventHandlers[data.type];
            
            if (handler) {
                handler(data);
            } else {
                console.warn('Unknown message type:', data.type, data);
            }
            
        } catch (error) {
            console.error('Error parsing WebSocket message:', error, event.data);
        }
    }

    handleClose(event) {
        console.log('Notification WebSocket disconnected:', event.code, event.reason);
        
        // Clear ping interval
        this.stopPingInterval();
        
        // Dispatch custom event for disconnection
        this.dispatchEvent('websocket_disconnected', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
        });
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000) {
            this.scheduleReconnect();
        }
    }

    handleError(error) {
        console.error('Notification WebSocket error:', error);
        this.dispatchEvent('websocket_error', { error: error });
    }

    handleNotification(data) {
        console.log('Received notification:', data);
        
        // Update unread count badge
        this.updateUnreadBadge(data.unread_count);
        
        // Show desktop notification if permission granted
        this.showDesktopNotification(data);
        
        // Show in-app notification toast
        this.showInAppNotification(data);
        
        // Play notification sound if enabled
        this.playNotificationSound();
        
        // Dispatch custom event for new notification
        this.dispatchEvent('notification_received', data);
    }

    handleOrderUpdate(data) {
        console.log('Order update:', data);
        
        // Show order update notification
        this.showToastNotification({
            title: 'Order Update',
            message: data.message,
            type: 'info',
            icon: 'fas fa-shopping-cart',
            actionUrl: data.action_url
        });
        
        // Dispatch custom event
        this.dispatchEvent('order_update_received', data);
    }

    handleNewMessage(data) {
        console.log('New message:', data);
        
        // Update message badge if exists
        this.updateMessageBadge();
        
        // Show message notification
        this.showToastNotification({
            title: `New Message from ${data.sender_name}`,
            message: data.preview,
            type: 'info',
            icon: 'fas fa-envelope',
            actionUrl: data.action_url
        });
        
        // Dispatch custom event
        this.dispatchEvent('new_message_received', data);
    }

    handlePaymentUpdate(data) {
        console.log('Payment update:', data);
        
        // Show payment notification
        this.showToastNotification({
            title: 'Payment Update',
            message: data.message,
            type: data.status === 'failed' ? 'error' : 'success',
            icon: 'fas fa-credit-card',
            actionUrl: data.action_url
        });
        
        // Dispatch custom event
        this.dispatchEvent('payment_update_received', data);
    }

    handleSystemAlert(data) {
        console.log('System alert:', data);
        
        // Show system alert
        this.showToastNotification({
            title: data.title || 'System Alert',
            message: data.message,
            type: data.alert_type || 'warning',
            icon: 'fas fa-exclamation-triangle',
            autoClose: false  // Don't auto-close important alerts
        });
        
        // Dispatch custom event
        this.dispatchEvent('system_alert_received', data);
    }

    handleUnreadCountUpdate(data) {
        console.log('Unread count update:', data.count);
        this.updateUnreadBadge(data.count);
        this.dispatchEvent('unread_count_updated', data);
    }

    handleNotificationRead(data) {
        console.log('Notification read:', data.notification_id);
        this.updateUnreadBadge(data.unread_count);
        this.dispatchEvent('notification_read', data);
    }

    handleInitialData(data) {
        console.log('Initial data:', data);
        this.updateUnreadBadge(data.unread_count);
        this.dispatchEvent('initial_data_received', data);
    }

    handlePreferencesUpdated(data) {
        console.log('Preferences updated:', data);
        this.dispatchEvent('preferences_updated', data);
    }

    handlePong(data) {
        console.log('Pong received:', data.timestamp);
        this.dispatchEvent('pong_received', data);
    }

    handleSubscribed(data) {
        console.log('Subscribed to categories:', data.categories);
        this.dispatchEvent('categories_subscribed', data);
    }

    handleUnsubscribed(data) {
        console.log('Unsubscribed from categories:', data.categories);
        this.dispatchEvent('categories_unsubscribed', data);
    }

    // Utility methods
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected, cannot send:', data);
        }
    }

    markAsRead(notificationId) {
        this.send({
            type: 'mark_read',
            notification_id: notificationId
        });
    }

    markAllAsRead() {
        this.send({
            type: 'mark_all_read'
        });
    }

    getUnreadCount() {
        this.send({
            type: 'get_unread_count'
        });
    }

    updatePreferences(preferences) {
        this.send({
            type: 'update_preferences',
            preferences: preferences
        });
    }

    subscribeToCategories(categories) {
        this.send({
            type: 'subscribe',
            categories: categories
        });
    }

    unsubscribeFromCategories(categories) {
        this.send({
            type: 'unsubscribe',
            categories: categories
        });
    }

    startPingInterval() {
        // Clear existing interval
        this.stopPingInterval();
        
        // Send ping every 30 seconds to keep connection alive
        this.pingInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.send({
                    type: 'ping',
                    timestamp: new Date().toISOString()
                });
            }
        }, 30000);
    }

    stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
            
            console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
            
            setTimeout(() => {
                console.log('Attempting to reconnect...');
                this.connect();
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
            this.dispatchEvent('max_reconnect_attempts_reached');
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close(1000, 'User initiated disconnect');
            this.socket = null;
        }
        this.stopPingInterval();
    }

    // UI Update Methods
    updateUnreadBadge(count) {
        // Update the unread badge in the navbar
        const badge = document.querySelector('.notification-badge, .unread-count-badge');
        if (badge) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = count > 0 ? 'inline-block' : 'none';
        }
        
        // Update page title if there are unread notifications
        if (count > 0) {
            const originalTitle = document.title.replace(/^\(\d+\)\s*/, '');
            document.title = `(${count}) ${originalTitle}`;
        } else {
            document.title = document.title.replace(/^\(\d+\)\s*/, '');
        }
    }

    updateMessageBadge() {
        // Update message badge if exists
        const messageBadge = document.querySelector('.message-badge, .message-count');
        if (messageBadge) {
            const currentCount = parseInt(messageBadge.textContent) || 0;
            messageBadge.textContent = currentCount + 1;
            messageBadge.style.display = 'inline-block';
        }
    }

    showDesktopNotification(data) {
        // Check if desktop notifications are supported and permitted
        if (!('Notification' in window)) {
            return;
        }
        
        if (Notification.permission === 'granted') {
            const notification = new Notification(data.title, {
                body: data.message,
                icon: '/static/favicon.ico',
                tag: `notification_${data.id}`,
                requireInteraction: data.priority >= 3, // High priority notifications require interaction
                data: {
                    actionUrl: data.action_url,
                    notificationId: data.id
                }
            });
            
            notification.onclick = function(event) {
                event.preventDefault();
                if (this.data.actionUrl) {
                    window.focus();
                    window.location.href = this.data.actionUrl;
                }
                this.close();
            };
            
            // Auto-close after 10 seconds for normal priority notifications
            if (data.priority < 3) {
                setTimeout(() => notification.close(), 10000);
            }
        }
    }

    showInAppNotification(data) {
        // Create notification element
        const notificationEl = document.createElement('div');
        notificationEl.className = `notification-toast alert alert-${this.getAlertType(data.notification_type)} alert-dismissible fade show`;
        notificationEl.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 1050; min-width: 300px; max-width: 400px;';
        
        notificationEl.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="me-2">
                    <i class="${this.getNotificationIcon(data.notification_type)}"></i>
                </div>
                <div class="flex-grow-1">
                    <h6 class="mb-1">${this.escapeHtml(data.title)}</h6>
                    <p class="mb-2 small">${this.escapeHtml(data.message)}</p>
                    ${data.action_url ? `<a href="${data.action_url}" class="btn btn-sm btn-outline-primary">${data.action_text || 'View'}</a>` : ''}
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Add to page
        document.body.appendChild(notificationEl);
        
        // Auto-remove after 8 seconds for normal priority
        if (data.priority < 3) {
            setTimeout(() => {
                if (notificationEl.parentNode) {
                    notificationEl.remove();
                }
            }, 8000);
        }
    }

    showToastNotification(options) {
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${options.type || 'info'} border-0`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="${options.icon || 'fas fa-bell'} me-2"></i>
                    <strong>${this.escapeHtml(options.title)}</strong><br>
                    <small>${this.escapeHtml(options.message)}</small>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        // Add to toast container or create one
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.appendChild(toastEl);
        
        // Initialize Bootstrap toast
        const toast = new bootstrap.Toast(toastEl, {
            autohide: options.autoClose !== false,
            delay: 5000
        });
        toast.show();
        
        // Add click handler for action URL
        if (options.actionUrl) {
            toastEl.addEventListener('click', (e) => {
                if (!e.target.closest('.btn-close')) {
                    window.location.href = options.actionUrl;
                }
            });
        }
        
        // Remove element after hide
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });
    }

    playNotificationSound() {
        // Check if sound is enabled in user preferences
        const soundEnabled = localStorage.getItem('notification_sound_enabled') !== 'false';
        
        if (soundEnabled) {
            const audio = new Audio('/static/sounds/notification.mp3');
            audio.volume = 0.3;
            audio.play().catch(e => console.log('Audio play failed:', e));
        }
    }

    // Helper methods
    getAlertType(notificationType) {
        const typeMap = {
            'info': 'info',
            'warning': 'warning',
            'alert': 'danger',
            'success': 'success',
            'error': 'danger'
        };
        return typeMap[notificationType] || 'info';
    }

    getNotificationIcon(notificationType) {
        const iconMap = {
            'info': 'fas fa-info-circle text-info',
            'warning': 'fas fa-exclamation-triangle text-warning',
            'alert': 'fas fa-exclamation-circle text-danger',
            'success': 'fas fa-check-circle text-success',
            'error': 'fas fa-times-circle text-danger'
        };
        return iconMap[notificationType] || 'fas fa-bell text-info';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    dispatchEvent(eventName, data) {
        // Dispatch custom event on document
        const event = new CustomEvent(`notification:${eventName}`, { detail: data });
        document.dispatchEvent(event);
    }
}

// Global instance
let notificationWebSocket = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is authenticated
    const isAuthenticated = document.body.getAttribute('data-user-authenticated') === 'true';
    
    if (isAuthenticated) {
        notificationWebSocket = new NotificationWebSocket();
        notificationWebSocket.connect();
        
        // Request desktop notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        
        // Make instance available globally for debugging
        window.notificationWebSocket = notificationWebSocket;
    }
});

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (notificationWebSocket && document.visibilityState === 'visible') {
        // Refresh unread count when page becomes visible
        notificationWebSocket.getUnreadCount();
    }
});