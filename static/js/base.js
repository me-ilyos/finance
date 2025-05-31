/**
 * Base Template JavaScript
 * Handles sidebar toggle functionality and state persistence
 */

window.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.querySelector('#sidebarToggle');
    const wrapper = document.querySelector('#wrapper');
    
    if (sidebarToggle && wrapper) {
        // Check for saved sidebar state in localStorage
        if (localStorage.getItem('sidebarToggled') === 'true') {
            wrapper.classList.add('toggled');
        }

        // Add click event listener for sidebar toggle
        sidebarToggle.addEventListener('click', function(event) {
            event.preventDefault();
            wrapper.classList.toggle('toggled');
            
            // Save the state to localStorage
            const isToggled = wrapper.classList.contains('toggled');
            localStorage.setItem('sidebarToggled', isToggled.toString());
        });
    }
    
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (window.bootstrap && tooltipTriggerList.length > 0) {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Initialize Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    if (window.bootstrap && popoverTriggerList.length > 0) {
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
}); 