// Main JavaScript for AI Tools

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

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Character counter for textareas
    document.querySelectorAll('[data-character-counter]').forEach(function(textarea) {
        const counterId = textarea.getAttribute('data-character-counter');
        const counter = document.getElementById(counterId);
        
        if (counter) {
            function updateCounter() {
                const max = parseInt(textarea.getAttribute('maxlength')) || 5000;
                const current = textarea.value.length;
                counter.textContent = `${current}/${max}`;
                
                if (current > max * 0.9) {
                    counter.classList.add('text-danger');
                    counter.classList.remove('text-warning');
                } else if (current > max * 0.7) {
                    counter.classList.add('text-warning');
                    counter.classList.remove('text-danger');
                } else {
                    counter.classList.remove('text-danger', 'text-warning');
                }
            }
            
            textarea.addEventListener('input', updateCounter);
            updateCounter(); // Initial update
        }
    });

    // Form validation enhancement
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Add Bootstrap validation classes
                form.classList.add('was-validated');
                
                // Scroll to first error
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center'
                    });
                    firstInvalid.focus();
                }
            }
        }, false);
    });

    // Copy to clipboard functionality
    document.querySelectorAll('[data-copy-target]').forEach(function(button) {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-copy-target');
            const target = document.getElementById(targetId);
            
            if (target) {
                navigator.clipboard.writeText(target.value || target.textContent)
                    .then(function() {
                        // Show success feedback
                        const originalHTML = button.innerHTML;
                        button.innerHTML = '<i class="fas fa-check"></i> Copied!';
                        button.classList.add('btn-success');
                        button.classList.remove('btn-primary');
                        
                        setTimeout(function() {
                            button.innerHTML = originalHTML;
                            button.classList.remove('btn-success');
                            button.classList.add('btn-primary');
                        }, 2000);
                    })
                    .catch(function(err) {
                        console.error('Could not copy text: ', err);
                        alert('Failed to copy text to clipboard');
                    });
            }
        });
    });

    // Auto-save for long forms
    let autoSaveTimer;
    document.querySelectorAll('[data-autosave]').forEach(function(textarea) {
        textarea.addEventListener('input', function() {
            clearTimeout(autoSaveTimer);
            
            autoSaveTimer = setTimeout(function() {
                // Implement auto-save logic here
                console.log('Auto-saving...');
                
                // Show save indicator
                const indicator = document.getElementById('saveIndicator');
                if (indicator) {
                    indicator.classList.remove('d-none');
                    setTimeout(function() {
                        indicator.classList.add('d-none');
                    }, 2000);
                }
            }, 2000); // Save 2 seconds after last input
        });
    });

    // Tab persistence
    document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(function(tab) {
        tab.addEventListener('shown.bs.tab', function(event) {
            localStorage.setItem('activeTab', event.target.getAttribute('href'));
        });
    });

    const activeTab = localStorage.getItem('activeTab');
    if (activeTab) {
        const tabTrigger = document.querySelector(`[href="${activeTab}"]`);
        if (tabTrigger) {
            new bootstrap.Tab(tabTrigger).show();
        }
    }

    // Word count functionality
    window.countWords = function(text) {
        if (!text || text.trim() === '') return 0;
        
        // Remove extra whitespace and count words
        return text.trim()
            .replace(/\s+/g, ' ')
            .split(' ')
            .filter(word => word.length > 0)
            .length;
    };

    // Text statistics
    window.getTextStats = function(text) {
        const words = window.countWords(text);
        const characters = text.length;
        const sentences = (text.match(/[.!?]+/g) || []).length;
        const paragraphs = (text.match(/\n\s*\n/g) || []).length + 1;
        
        return {
            words: words,
            characters: characters,
            sentences: sentences,
            paragraphs: paragraphs,
            readingTime: Math.ceil(words / 200) // 200 words per minute
        };
    };

    // Export functions for use in other scripts
    window.AIToolsUtils = {
        countWords: window.countWords,
        getTextStats: window.getTextStats,
        formatNumber: function(num) {
            return new Intl.NumberFormat().format(num);
        }
    };
});

// Error handling
window.addEventListener('error', function(event) {
    console.error('Global error caught:', event.error);
    
    // Show user-friendly error message
    const errorDiv = document.getElementById('global-error');
    if (errorDiv) {
        errorDiv.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>An error occurred:</strong> ${event.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        errorDiv.classList.remove('d-none');
    }
});

// Offline detection
window.addEventListener('offline', function() {
    const alert = document.createElement('div');
    alert.className = 'alert alert-warning alert-dismissible fade show fixed-top m-3';
    alert.innerHTML = `
        <i class="fas fa-wifi-slash"></i>
        <strong>You are offline.</strong> Some features may not work.
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alert);
});

window.addEventListener('online', function() {
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show fixed-top m-3';
    alert.innerHTML = `
        <i class="fas fa-wifi"></i>
        <strong>You are back online.</strong> All features restored.
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alert);
    
    setTimeout(function() {
        bootstrap.Alert.getInstance(alert).close();
    }, 3000);
});