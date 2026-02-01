/**
 * Orders-specific JavaScript functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Order form validation
    var orderForm = document.getElementById('orderForm');
    if (orderForm) {
        orderForm.addEventListener('submit', function(e) {
            var words = parseInt(document.getElementById('id_words').value) || 0;
            var pages = parseInt(document.getElementById('id_pages').value) || 1;
            
            // Validate word count vs pages
            var expectedWordsMin = (pages - 1) * 275 + 1;
            var expectedWordsMax = pages * 275 + 100;
            
            if (words < expectedWordsMin) {
                e.preventDefault();
                alert(`Word count seems low for ${pages} page(s). Expected at least ${expectedWordsMin} words.`);
                document.getElementById('id_words').focus();
                return false;
            }
            
            if (words > expectedWordsMax) {
                e.preventDefault();
                alert(`Word count seems high for ${pages} page(s). Expected around ${pages * 275} words (±100).`);
                document.getElementById('id_words').focus();
                return false;
            }
            
            // Validate deadline
            var deadlineInput = document.getElementById('id_deadline');
            if (deadlineInput) {
                var deadline = new Date(deadlineInput.value);
                var now = new Date();
                
                if (deadline <= now) {
                    e.preventDefault();
                    alert('Deadline must be in the future.');
                    deadlineInput.focus();
                    return false;
                }
            }
        });
    }
    
    // Price calculator
    function calculateOrderPrice() {
        var academicLevel = document.getElementById('id_academic_level');
        var words = parseInt(document.getElementById('id_words').value) || 0;
        var urgency = document.getElementById('id_urgency');
        var priceInput = document.getElementById('id_price');
        
        if (academicLevel && words > 0 && urgency && priceInput) {
            var baseRates = {
                'high_school': 0.05,
                'undergraduate': 0.08,
                'bachelors': 0.10,
                'masters': 0.15,
                'phd': 0.20,
                'professional': 0.25
            };
            
            var urgencyMultipliers = {
                'standard': 1.0,
                'urgent': 1.5,
                'very_urgent': 2.0,
                'emergency': 3.0
            };
            
            var baseRate = baseRates[academicLevel.value] || 0.08;
            var multiplier = urgencyMultipliers[urgency.value] || 1.0;
            
            var suggestedPrice = words * baseRate * multiplier;
            
            // Update price suggestions
            var priceSuggestions = document.getElementById('priceSuggestions');
            if (priceSuggestions) {
                var minPrice = (suggestedPrice * 0.5).toFixed(2);
                var maxPrice = (suggestedPrice * 2).toFixed(2);
                priceSuggestions.innerHTML = `$${minPrice} - $${maxPrice} (Suggested: $${suggestedPrice.toFixed(2)})`;
            }
            
            // Auto-fill price if empty
            if (!priceInput.value || parseFloat(priceInput.value) === 0) {
                priceInput.value = suggestedPrice.toFixed(2);
            }
        }
    }
    
    // Bind price calculator events
    var priceCalcInputs = ['id_academic_level', 'id_words', 'id_urgency'];
    priceCalcInputs.forEach(function(id) {
        var element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', calculateOrderPrice);
            element.addEventListener('input', calculateOrderPrice);
        }
    });
    
    // Initialize price calculator
    calculateOrderPrice();
    
    // Order status timeline
    function updateOrderTimeline() {
        var timelineItems = document.querySelectorAll('.timeline-item');
        timelineItems.forEach(function(item, index) {
            item.style.animationDelay = (index * 0.2) + 's';
        });
    }
    
    updateOrderTimeline();
    
    // Order countdown timer
    function updateOrderCountdown() {
        var countdownElements = document.querySelectorAll('.order-countdown');
        
        countdownElements.forEach(function(element) {
            var deadline = new Date(element.dataset.deadline);
            var now = new Date();
            var diff = deadline - now;
            
            if (diff > 0) {
                var days = Math.floor(diff / (1000 * 60 * 60 * 24));
                var hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                var minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                
                element.textContent = days + 'd ' + hours + 'h ' + minutes + 'm';
                
                // Color coding based on urgency
                if (days === 0 && hours < 24) {
                    element.classList.add('text-warning');
                }
                if (days === 0 && hours < 6) {
                    element.classList.remove('text-warning');
                    element.classList.add('text-danger');
                }
            } else {
                element.textContent = 'OVERDUE';
                element.classList.add('text-danger');
                element.classList.add('fw-bold');
            }
        });
    }
    
    // Update countdown every minute
    updateOrderCountdown();
    setInterval(updateOrderCountdown, 60000);
    
    // Order search functionality
    var orderSearchInput = document.getElementById('orderSearch');
    if (orderSearchInput) {
        var debouncedSearch = debounce(function() {
            var searchTerm = orderSearchInput.value;
            if (searchTerm.length >= 2) {
                performOrderSearch(searchTerm);
            }
        }, 500);
        
        orderSearchInput.addEventListener('input', debouncedSearch);
    }
    
    // Order filters
    var orderFilters = document.querySelectorAll('.order-filter');
    orderFilters.forEach(function(filter) {
        filter.addEventListener('change', function() {
            applyOrderFilters();
        });
    });
    
    // Order actions confirmation
    var orderActionButtons = document.querySelectorAll('.order-action-btn');
    orderActionButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            var action = this.dataset.action;
            var orderNumber = this.dataset.orderNumber;
            var confirmationMessage = this.dataset.confirm || `Are you sure you want to ${action} order ${orderNumber}?`;
            
            if (!confirm(confirmationMessage)) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    });
    
    // File upload progress
    var fileUploadInputs = document.querySelectorAll('input[type="file"][multiple]');
    fileUploadInputs.forEach(function(input) {
        input.addEventListener('change', function(e) {
            var files = e.target.files;
            var totalSize = 0;
            var maxSize = 20 * 1024 * 1024; // 20MB per file
            var maxTotalSize = 100 * 1024 * 1024; // 100MB total
            
            for (var i = 0; i < files.length; i++) {
                totalSize += files[i].size;
                
                // Check individual file size
                if (files[i].size > maxSize) {
                    alert(`File "${files[i].name}" exceeds 20MB limit.`);
                    this.value = '';
                    return;
                }
            }
            
            // Check total size
            if (totalSize > maxTotalSize) {
                alert(`Total file size exceeds 100MB limit.`);
                this.value = '';
            }
            
            // Show file count
            var fileCountElement = this.nextElementSibling;
            if (fileCountElement && fileCountElement.classList.contains('file-count')) {
                fileCountElement.textContent = files.length + ' file(s) selected';
            }
        });
    });
    
    // Order checklist validation
    var checklistForms = document.querySelectorAll('.checklist-form');
    checklistForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            var requiredCheckboxes = form.querySelectorAll('input[type="checkbox"][required]');
            var allChecked = true;
            
            requiredCheckboxes.forEach(function(checkbox) {
                if (!checkbox.checked) {
                    allChecked = false;
                    checkbox.classList.add('is-invalid');
                } else {
                    checkbox.classList.remove('is-invalid');
                }
            });
            
            if (!allChecked) {
                e.preventDefault();
                alert('Please complete all required quality checks before submitting.');
                return false;
            }
        });
    });
    
    // Order progress bar animation
    var progressBars = document.querySelectorAll('.order-progress');
    progressBars.forEach(function(bar) {
        var width = bar.style.width || bar.dataset.width || '0%';
        bar.style.width = '0%';
        
        setTimeout(function() {
            bar.style.transition = 'width 1s ease-in-out';
            bar.style.width = width;
        }, 300);
    });
    
    // Order assignment wizard
    var assignmentWizard = document.getElementById('assignmentWizard');
    if (assignmentWizard) {
        var steps = assignmentWizard.querySelectorAll('.wizard-step');
        var currentStep = 0;
        
        function showStep(stepIndex) {
            steps.forEach(function(step, index) {
                step.classList.toggle('d-none', index !== stepIndex);
            });
            
            // Update progress
            var progress = ((stepIndex + 1) / steps.length) * 100;
            var progressBar = assignmentWizard.querySelector('.wizard-progress');
            if (progressBar) {
                progressBar.style.width = progress + '%';
            }
        }
        
        // Next/Previous buttons
        assignmentWizard.querySelectorAll('.wizard-next').forEach(function(button) {
            button.addEventListener('click', function() {
                if (currentStep < steps.length - 1) {
                    currentStep++;
                    showStep(currentStep);
                }
            });
        });
        
        assignmentWizard.querySelectorAll('.wizard-prev').forEach(function(button) {
            button.addEventListener('click', function() {
                if (currentStep > 0) {
                    currentStep--;
                    showStep(currentStep);
                }
            });
        });
        
        // Initialize
        showStep(0);
    }
    
    // Order chat/messaging
    var orderChat = document.getElementById('orderChat');
    if (orderChat) {
        var chatMessages = orderChat.querySelector('.chat-messages');
        var chatInput = orderChat.querySelector('.chat-input');
        var chatSendBtn = orderChat.querySelector('.chat-send-btn');
        
        function scrollToBottom() {
            if (chatMessages) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }
        
        function sendMessage() {
            var message = chatInput.value.trim();
            if (message) {
                // Add message to chat (this would be an AJAX call in production)
                var messageElement = document.createElement('div');
                messageElement.className = 'chat-message sent';
                messageElement.innerHTML = `
                    <div class="message-content">${message}</div>
                    <div class="message-time">Just now</div>
                `;
                
                chatMessages.appendChild(messageElement);
                chatInput.value = '';
                scrollToBottom();
                
                // Simulate response (would be via WebSocket in production)
                setTimeout(function() {
                    var responseElement = document.createElement('div');
                    responseElement.className = 'chat-message received';
                    responseElement.innerHTML = `
                        <div class="message-content">Thank you for your message. We'll get back to you shortly.</div>
                        <div class="message-time">Just now</div>
                    `;
                    chatMessages.appendChild(responseElement);
                    scrollToBottom();
                }, 1000);
            }
        }
        
        if (chatSendBtn) {
            chatSendBtn.addEventListener('click', sendMessage);
        }
        
        if (chatInput) {
            chatInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
        
        scrollToBottom();
    }
    
    // Order export functionality
    var exportButtons = document.querySelectorAll('.export-order-data');
    exportButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var orderId = this.dataset.orderId;
            var format = this.dataset.format || 'pdf';
            
            // Show loading
            var originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Exporting...';
            this.disabled = true;
            
            // Simulate export (would be AJAX in production)
            setTimeout(function() {
                showToast('Export completed successfully', 'success');
                button.innerHTML = originalText;
                button.disabled = false;
            }, 1500);
        });
    });
    
    // Order reminder functionality
    var reminderButtons = document.querySelectorAll('.set-reminder');
    reminderButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var orderId = this.dataset.orderId;
            var reminderTime = prompt('Set reminder time (in hours):', '24');
            
            if (reminderTime && !isNaN(reminderTime)) {
                // This would be an AJAX call in production
                showToast(`Reminder set for ${reminderTime} hours`, 'success');
            }
        });
    });
    
    // Order notes functionality
    var noteButtons = document.querySelectorAll('.add-note');
    noteButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var orderId = this.dataset.orderId;
            var noteText = prompt('Add a note for this order:');
            
            if (noteText) {
                // This would be an AJAX call in production
                showToast('Note added successfully', 'success');
            }
        });
    });
});

// Order search function
function performOrderSearch(searchTerm) {
    // This would be an AJAX call in production
    console.log('Searching for:', searchTerm);
    
    // Example AJAX implementation:
    /*
    ajaxRequest(`/orders/search/?q=${encodeURIComponent(searchTerm)}`)
        .then(function(response) {
            updateSearchResults(response.results);
        })
        .catch(function(error) {
            console.error('Search error:', error);
            showToast('Search failed. Please try again.', 'error');
        });
    */
}

// Apply order filters
function applyOrderFilters() {
    var filters = {};
    var filterElements = document.querySelectorAll('.order-filter:checked');
    
    filterElements.forEach(function(element) {
        var name = element.name;
        var value = element.value;
        
        if (!filters[name]) {
            filters[name] = [];
        }
        filters[name].push(value);
    });
    
    // Build query string
    var queryParams = [];
    for (var key in filters) {
        filters[key].forEach(function(value) {
            queryParams.push(key + '=' + encodeURIComponent(value));
        });
    }
    
    // This would update the URL or make an AJAX call
    if (queryParams.length > 0) {
        var newUrl = window.location.pathname + '?' + queryParams.join('&');
        // window.location.href = newUrl; // Or use AJAX
    }
}

// Update order status via AJAX
function updateOrderStatus(orderId, newStatus) {
    return ajaxRequest(`/api/orders/${orderId}/status/`, 'PATCH', {
        status: newStatus
    })
    .then(function(response) {
        showToast('Order status updated successfully', 'success');
        return response;
    })
    .catch(function(error) {
        showToast('Failed to update order status', 'error');
        throw error;
    });
}

// Get available writers for order
function getAvailableWriters(orderId) {
    return ajaxRequest(`/api/orders/${orderId}/available-writers/`)
        .then(function(response) {
            return response.writers;
        })
        .catch(function(error) {
            console.error('Failed to get available writers:', error);
            return [];
        });
}

// Calculate order statistics
function calculateOrderStats(orders) {
    var stats = {
        total: orders.length,
        completed: 0,
        inProgress: 0,
        overdue: 0,
        totalRevenue: 0
    };
    
    orders.forEach(function(order) {
        if (order.status === 'completed') stats.completed++;
        if (order.status === 'in_progress') stats.inProgress++;
        if (order.is_overdue) stats.overdue++;
        stats.totalRevenue += parseFloat(order.price) || 0;
    });
    
    return stats;
}

// Format order data for display
function formatOrderData(order) {
    return {
        id: order.id,
        number: order.order_number,
        title: order.title,
        client: order.client_name || order.client_email,
        writer: order.writer_name || order.writer_email || 'Not assigned',
        status: order.status,
        status_display: order.status_display,
        deadline: new Date(order.deadline),
        formatted_deadline: formatDate(order.deadline),
        price: formatCurrency(order.price),
        writer_payment: formatCurrency(order.writer_payment),
        platform_fee: formatCurrency(order.platform_fee),
        is_overdue: order.is_overdue || false,
        progress: order.progress_percentage || 0,
        revision_count: order.revision_count || 0,
        max_revisions: order.max_revisions || 3
    };
}

// Export order data
function exportOrderData(orderId, format) {
    var url = `/orders/${orderId}/export/?format=${format}`;
    window.open(url, '_blank');
}

// Initialize real-time order updates (WebSocket)
function initializeOrderUpdates() {
    // This would connect to WebSocket for real-time updates
    /*
    var socket = new WebSocket(`wss://${window.location.host}/ws/orders/`);
    
    socket.onmessage = function(event) {
        var data = JSON.parse(event.data);
        if (data.type === 'order_update') {
            updateOrderUI(data.order);
        }
    };
    
    socket.onclose = function() {
        console.log('WebSocket connection closed');
    };
    */
}

// Update order UI after real-time update
function updateOrderUI(orderData) {
    var orderElement = document.querySelector(`[data-order-id="${orderData.id}"]`);
    if (orderElement) {
        // Update status
        var statusElement = orderElement.querySelector('.order-status');
        if (statusElement) {
            statusElement.textContent = orderData.status_display;
            statusElement.className = 'order-status badge bg-' + (orderData.status === 'completed' ? 'success' : 'warning');
        }
        
        // Update progress
        var progressElement = orderElement.querySelector('.order-progress');
        if (progressElement) {
            progressElement.style.width = orderData.progress + '%';
        }
        
        // Update countdown
        var countdownElement = orderElement.querySelector('.order-countdown');
        if (countdownElement) {
            var deadline = new Date(orderData.deadline);
            var now = new Date();
            var diff = deadline - now;
            
            if (diff > 0) {
                var days = Math.floor(diff / (1000 * 60 * 60 * 24));
                countdownElement.textContent = days + 'd left';
            } else {
                countdownElement.textContent = 'OVERDUE';
                countdownElement.className = 'order-countdown text-danger fw-bold';
            }
        }
        
        showToast(`Order ${orderData.number} updated`, 'info');
    }
}

// Order validation rules
var orderValidationRules = {
    title: {
        required: true,
        minLength: 10,
        maxLength: 500
    },
    description: {
        required: true,
        minLength: 50,
        maxLength: 5000
    },
    words: {
        required: true,
        min: 100,
        max: 50000
    },
    pages: {
        required: true,
        min: 1,
        max: 100
    },
    price: {
        required: true,
        min: 5
    },
    deadline: {
        required: true,
        futureDate: true
    }
};

// Validate order field
function validateOrderField(fieldName, value) {
    var rules = orderValidationRules[fieldName];
    if (!rules) return true;
    
    var errors = [];
    
    if (rules.required && !value) {
        errors.push('This field is required');
    }
    
    if (rules.minLength && value && value.length < rules.minLength) {
        errors.push(`Minimum length is ${rules.minLength} characters`);
    }
    
    if (rules.maxLength && value && value.length > rules.maxLength) {
        errors.push(`Maximum length is ${rules.maxLength} characters`);
    }
    
    if (rules.min && value && parseFloat(value) < rules.min) {
        errors.push(`Minimum value is ${rules.min}`);
    }
    
    if (rules.max && value && parseFloat(value) > rules.max) {
        errors.push(`Maximum value is ${rules.max}`);
    }
    
    if (rules.futureDate && value) {
        var date = new Date(value);
        var now = new Date();
        if (date <= now) {
            errors.push('Date must be in the future');
        }
    }
    
    return errors;
}

// Validate entire order form
function validateOrderForm(formData) {
    var errors = {};
    
    for (var field in orderValidationRules) {
        var fieldErrors = validateOrderField(field, formData[field]);
        if (fieldErrors.length > 0) {
            errors[field] = fieldErrors;
        }
    }
    
    return {
        isValid: Object.keys(errors).length === 0,
        errors: errors
    };
}

// Display form errors
function displayFormErrors(errors) {
    for (var field in errors) {
        var inputElement = document.getElementById('id_' + field);
        if (inputElement) {
            var errorElement = inputElement.nextElementSibling;
            if (!errorElement || !errorElement.classList.contains('invalid-feedback')) {
                errorElement = document.createElement('div');
                errorElement.className = 'invalid-feedback';
                inputElement.parentNode.appendChild(errorElement);
            }
            
            errorElement.textContent = errors[field].join(', ');
            inputElement.classList.add('is-invalid');
        }
    }
}