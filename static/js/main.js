/**
 * AI Lead Automation - Main JavaScript File
 * Common utilities and functions for the application
 */

// Global configuration
const AppConfig = {
    apiBaseUrl: '/api',
    refreshInterval: 30000, // 30 seconds
    notificationDuration: 5000, // 5 seconds
    chartColors: {
        primary: '#667eea',
        secondary: '#764ba2',
        success: '#48bb78',
        warning: '#f6ad55',
        danger: '#fc8181',
        info: '#63b3ed'
    }
};

// Utility functions
const Utils = {
    /**
     * Format date to readable string
     */
    formatDate: (dateString) => {
        const date = new Date(dateString);
        return date.toLocaleString();
    },

    /**
     * Format number with commas
     */
    formatNumber: (num) => {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    },

    /**
     * Get percentage color based on value
     */
    getPercentageColor: (value) => {
        if (value >= 80) return 'success';
        if (value >= 60) return 'warning';
        return 'danger';
    },

    /**
     * Debounce function
     */
    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Copy text to clipboard
     */
    copyToClipboard: async (text) => {
        try {
            await navigator.clipboard.writeText(text);
            Notification.show('Copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            Notification.show('Failed to copy to clipboard', 'error');
        }
    },

    /**
     * Download data as JSON file
     */
    downloadJSON: (data, filename) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    /**
     * Validate email format
     */
    validateEmail: (email) => {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    /**
     * Generate random ID
     */
    generateId: () => {
        return Math.random().toString(36).substr(2, 9);
    }
};

// Notification system
const Notification = {
    /**
     * Show notification message
     */
    show: (message, type = 'info', duration = AppConfig.notificationDuration) => {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 500px;';
        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${this.getIcon(type)} me-2"></i>
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
    },

    /**
     * Get icon for notification type
     */
    getIcon: (type) => {
        switch(type) {
            case 'success': return 'check-circle';
            case 'error': return 'exclamation-circle';
            case 'warning': return 'exclamation-triangle';
            default: return 'info-circle';
        }
    }
};

// API service
const API = {
    /**
     * Make API request
     */
    request: async (endpoint, options = {}) => {
        const url = `${AppConfig.apiBaseUrl}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API request failed:', error);
            Notification.show('API request failed: ' + error.message, 'error');
            throw error;
        }
    },

    /**
     * GET request
     */
    get: (endpoint) => {
        return API.request(endpoint);
    },

    /**
     * POST request
     */
    post: (endpoint, data) => {
        return API.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    /**
     * PUT request
     */
    put: (endpoint, data) => {
        return API.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    /**
     * DELETE request
     */
    delete: (endpoint) => {
        return API.request(endpoint, {
            method: 'DELETE',
        });
    }
};

// Chart utilities
const ChartUtils = {
    /**
     * Create default chart options
     */
    getDefaultOptions: (type = 'line') => {
        const baseOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                }
            }
        };

        if (type === 'line' || type === 'bar') {
            baseOptions.scales = {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            };
        }

        return baseOptions;
    },

    /**
     * Create gradient colors for charts
     */
    createGradient: (ctx, color1, color2) => {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        return gradient;
    }
};

// Loading states
const Loading = {
    /**
     * Show loading state on element
     */
    show: (element) => {
        element.disabled = true;
        element.classList.add('loading');
        
        if (element.tagName === 'BUTTON') {
            const originalText = element.innerHTML;
            element.dataset.originalText = originalText;
            element.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
        }
    },

    /**
     * Hide loading state on element
     */
    hide: (element) => {
        element.disabled = false;
        element.classList.remove('loading');
        
        if (element.tagName === 'BUTTON' && element.dataset.originalText) {
            element.innerHTML = element.dataset.originalText;
            delete element.dataset.originalText;
        }
    },

    /**
     * Show loading spinner
     */
    spinner: (containerId) => {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="d-flex justify-content-center align-items-center" style="height: 200px;">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;
        }
    }
};

// Form validation
const Validation = {
    /**
     * Validate required fields
     */
    validateRequired: (form) => {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('is-invalid');
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
            }
        });

        return isValid;
    },

    /**
     * Validate email field
     */
    validateEmail: (emailField) => {
        const email = emailField.value.trim();
        const isValid = Utils.validateEmail(email);
        
        if (!isValid) {
            emailField.classList.add('is-invalid');
        } else {
            emailField.classList.remove('is-invalid');
        }
        
        return isValid;
    },

    /**
     * Clear all validation states
     */
    clearValidation: (form) => {
        const fields = form.querySelectorAll('.is-invalid, .is-valid');
        fields.forEach(field => {
            field.classList.remove('is-invalid', 'is-valid');
        });
    }
};

// Modal utilities
const Modal = {
    /**
     * Show confirmation modal
     */
    confirm: async (message, title = 'Confirm Action') => {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger" id="confirmBtn">Confirm</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            
            document.getElementById('confirmBtn').addEventListener('click', () => {
                bsModal.hide();
                resolve(true);
            });
            
            modal.addEventListener('hidden.bs.modal', () => {
                document.body.removeChild(modal);
                resolve(false);
            });
            
            bsModal.show();
        });
    }
};

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, AppConfig.notificationDuration);
    });

    // Handle form submissions with loading states
    const forms = document.querySelectorAll('form[data-loading]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                Loading.show(submitBtn);
            }
        });
    });

    console.log('AI Lead Automation initialized');
});

// Export for use in other files
window.AppConfig = AppConfig;
window.Utils = Utils;
window.Notification = Notification;
window.API = API;
window.ChartUtils = ChartUtils;
window.Loading = Loading;
window.Validation = Validation;
window.Modal = Modal;
