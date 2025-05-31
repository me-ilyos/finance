/**
 * Dashboard JavaScript
 * Handles account navigation, time updates, and keyboard interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Account selection functionality
    const accountItems = document.querySelectorAll('.account-item');
    
    accountItems.forEach(item => {
        item.addEventListener('click', function() {
            const url = this.getAttribute('data-account-url');
            if (url && !this.classList.contains('active')) {
                window.location.href = url;
            }
        });
        
        // Keyboard accessibility
        item.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });
    
    // Real-time clock update
    function updateTime() {
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            timeElement.textContent = timeString;
        }
    }
    
    // Update time every second
    setInterval(updateTime, 1000);
    
    // Keyboard navigation for accounts
    document.addEventListener('keydown', function(e) {
        const items = Array.from(document.querySelectorAll('.account-item'));
        const activeItem = document.querySelector('.account-item.active');
        
        if (items.length > 0 && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            e.preventDefault();
            
            let currentIndex = items.indexOf(activeItem);
            let targetIndex;
            
            if (e.key === 'ArrowDown') {
                targetIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % items.length;
            } else {
                targetIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
            }
            
            const targetItem = items[targetIndex];
            const url = targetItem.getAttribute('data-account-url');
            
            if (url) {
                window.location.href = url;
            }
        }
    });
    
    // Initialize tooltips if needed
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (window.bootstrap && tooltipTriggerList.length > 0) {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}); 