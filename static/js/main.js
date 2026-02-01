/**
 * Main JavaScript for EBWriting Platform
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Form validation
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // File upload preview
    var fileInputs = document.querySelectorAll('.file-input-preview');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function(e) {
            var fileName = e.target.files[0]?.name || 'No file chosen';
            var label = input.nextElementSibling;
            if (label && label.classList.contains('custom-file-label')) {
                label.textContent = fileName;
            }
        });
    });
    
    // Password strength indicator
    var passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            var strengthBar = document.getElementById('password-strength-bar');
            var strengthText = document.getElementById('password-strength-text');
            
            if (strengthBar && strengthText) {
                var password = input.value;
                var strength = 0;
                
                // Length check
                if (password.length >= 8) strength += 25;
                if (password.length >= 12) strength += 25;
                
                // Complexity checks
                if (/[A-Z]/.test(password)) strength += 25;
                if (/[0-9]/.test(password)) strength += 25;
                
                // Update progress bar
                strengthBar.style.width = strength + '%';
                strengthBar.setAttribute('aria-valuenow', strength);
                
                // Update text
                if (strength <= 25) {
                    strengthBar.className = 'progress-bar bg-danger';
                    strengthText.textContent = 'Weak';
                } else if (strength <= 50) {
                    strengthBar.className = 'progress-bar bg-warning';
                    strengthText.textContent = 'Fair';
                } else if (strength <= 75) {
                    strengthBar.className = 'progress-bar bg-info';
                    strengthText.textContent = 'Good';
                } else {
                    strengthBar.className = 'progress-bar bg-success';
                    strengthText.textContent = 'Strong';
                }
            }
        });
    });
    
    // Copy to clipboard functionality
    var copyButtons = document.querySelectorAll('[data-copy]');
    copyButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var targetId = this.getAttribute('data-copy');
            var targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                navigator.clipboard.writeText(targetElement.textContent || targetElement.value)
                    .then(function() {
                        // Show success feedback
                        var originalText = button.innerHTML;
                        button.innerHTML = '<i class="bi bi-check-circle me-1"></i>Copied!';
                        button.classList.add('btn-success');
                        
                        setTimeout(function() {
                            button.innerHTML = originalText;
                            button.classList.remove('btn-success');
                        }, 2000);
                    })
                    .catch(function(err) {
                        console.error('Failed to copy: ', err);
                    });
            }
        });
    });
    
    // Toggle password visibility
    var togglePasswordButtons = document.querySelectorAll('.toggle-password');
    togglePasswordButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var targetId = this.getAttribute('data-target');
            var passwordInput = document.getElementById(targetId);
            
            if (passwordInput) {
                var type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                
                // Toggle icon
                var icon = this.querySelector('i');
                if (icon) {
                    icon.className = type === 'password' ? 'bi bi-eye' : 'bi bi-eye-slash';
                }
            }
        });
    });
    
    // Auto-submit forms on select change
    var autoSubmitSelects = document.querySelectorAll('select[data-auto-submit]');
    autoSubmitSelects.forEach(function(select) {
        select.addEventListener('change', function() {
            this.form.submit();
        });
    });
    
    // Confirm before action
    var confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            var message = this.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    });
    
    // Show loading state on form submission
    var formsWithLoading = document.querySelectorAll('form[data-loading]');
    formsWithLoading.forEach(function(form) {
        form.addEventListener('submit', function() {
            var submitButton = this.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
            }
        });
    });
    
    // Initialize toast notifications
    var toastElList = [].slice.call(document.querySelectorAll('.toast'));
    var toastList = toastElList.map(function (toastEl) {
        return new bootstrap.Toast(toastEl);
    });
    
    // Show toast if there's a message
    if (document.querySelector('.toast')) {
        toastList[0].show();
    }
    
    // Table row click navigation
    var clickableRows = document.querySelectorAll('tr[data-href]');
    clickableRows.forEach(function(row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
            if (!e.target.matches('a, button, input, .btn, .no-click')) {
                window.location.href = this.dataset.href;
            }
        });
    });
    
    // Initialize charts if Chart.js is loaded
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
    
    // Theme switcher
    var themeSwitcher = document.getElementById('themeSwitcher');
    if (themeSwitcher) {
        themeSwitcher.addEventListener('click', function() {
            var currentTheme = document.documentElement.getAttribute('data-bs-theme');
            var newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            // Update icon
            var icon = this.querySelector('i');
            if (icon) {
                icon.className = newTheme === 'dark' ? 'bi bi-sun' : 'bi bi-moon';
            }
        });
        
        // Load saved theme
        var savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
    }
    
    // Dashboard-specific functionality
    initializeDashboard();
});

// Initialize dashboard-specific functionality
function initializeDashboard() {
    // Check if we're on a dashboard page
    const isDashboardPage = window.location.pathname.includes('dashboard') || 
                           document.querySelector('.dashboard-header') || 
                           document.querySelector('.stats-card');
    
    if (isDashboardPage) {
        // Auto-refresh dashboard stats every 60 seconds
        const refreshInterval = setInterval(function() {
            refreshDashboardStats();
        }, 60000);
        
        // Clean up interval when leaving page
        window.addEventListener('beforeunload', function() {
            clearInterval(refreshInterval);
        });
    }
}

// Refresh dashboard stats via AJAX
function refreshDashboardStats() {
    // Only refresh if user is active (tab focused)
    if (document.hidden) return;
    
    fetch('/api/dashboard/stats/', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        updateDashboardUI(data);
    })
    .catch(error => {
        console.log('Failed to refresh dashboard stats:', error);
    });
}

// Update dashboard UI with new data
function updateDashboardUI(data) {
    // Update stats cards
    const statsCards = document.querySelectorAll('.stats-value');
    statsCards.forEach(card => {
        const statType = card.closest('.stats-info')?.querySelector('.stats-label')?.textContent;
        if (statType && data[statType.toLowerCase().replace(' ', '_')]) {
            card.textContent = data[statType.toLowerCase().replace(' ', '_')];
        }
    });
    
    // Show notification if there are updates
    if (data.updated) {
        showToast('Dashboard updated', 'success');
    }
}

// Initialize charts function
function initializeCharts() {
    // Example: Order statistics chart
    var orderStatsCanvas = document.getElementById('orderStatsChart');
    if (orderStatsCanvas) {
        var ctx = orderStatsCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'In Progress', 'Pending', 'Cancelled'],
                datasets: [{
                    data: [65, 15, 10, 10],
                    backgroundColor: [
                        '#198754',
                        '#0dcaf0',
                        '#ffc107',
                        '#dc3545'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

// Utility function to format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Utility function to format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Utility function to show toast notification
function showToast(message, type = 'info') {
    var toastEl = document.getElementById('liveToast');
    var toastMessage = document.getElementById('toastMessage');
    var toastHeader = toastEl.querySelector('.toast-header i');
    
    if (toastMessage) {
        toastMessage.textContent = message;
        
        // Update icon based on type
        if (toastHeader) {
            switch(type) {
                case 'success':
                    toastHeader.className = 'bi bi-check-circle-fill text-success me-2';
                    break;
                case 'error':
                    toastHeader.className = 'bi bi-exclamation-triangle-fill text-danger me-2';
                    break;
                case 'warning':
                    toastHeader.className = 'bi bi-exclamation-circle-fill text-warning me-2';
                    break;
                default:
                    toastHeader.className = 'bi bi-info-circle-fill text-info me-2';
            }
        }
        
        var toast = new bootstrap.Toast(toastEl);
        toast.show();
    }
}

// AJAX helper function
function ajaxRequest(url, method = 'GET', data = null) {
    return new Promise(function(resolve, reject) {
        var xhr = new XMLHttpRequest();
        xhr.open(method, url);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.setRequestHeader('Content-Type', 'application/json');
        
        xhr.onload = function() {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    var response = JSON.parse(xhr.responseText);
                    resolve(response);
                } catch (e) {
                    resolve(xhr.responseText);
                }
            } else {
                reject({
                    status: xhr.status,
                    statusText: xhr.statusText
                });
            }
        };
        
        xhr.onerror = function() {
            reject({
                status: xhr.status,
                statusText: xhr.statusText
            });
        };
        
        xhr.send(data ? JSON.stringify(data) : null);
    });
}

// Debounce function for search inputs
function debounce(func, wait) {
    var timeout;
    return function executedFunction() {
        var context = this;
        var args = arguments;
        var later = function() {
            timeout = null;
            func.apply(context, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Dashboard progress bar animation
function animateProgressBars() {
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.width = width;
        }, 500);
    });
}

// Initialize dashboard tabs
function initializeDashboardTabs() {
    const triggerTabList = [].slice.call(document.querySelectorAll('#analyticsTab button'));
    triggerTabList.forEach(function (triggerEl) {
        var tabTrigger = new bootstrap.Tab(triggerEl);
        
        triggerEl.addEventListener('click', function (event) {
            event.preventDefault();
            tabTrigger.show();
        });
    });
}