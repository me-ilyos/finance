// Function to add classes to form elements
function styleFormElements() {
    const form = document.getElementById('filter-form');
    if (!form) return;

    // Style text inputs
    const textInputs = form.querySelectorAll('input[type="text"], input[type="date"]');
    textInputs.forEach(input => {
        input.classList.add('form-control', 'form-control-sm'); 
    });

    // Style select inputs
    const selects = form.querySelectorAll('select');
    selects.forEach(select => {
        select.classList.add('form-select', 'form-select-sm');
    });
    
    // Style labels (optional, if they exist and need styling)
    const labels = form.querySelectorAll('label');
    labels.forEach(label => {
        // label.classList.add('form-label'); 
    });
}

// Common utility functions
function formatNumber(num) {
    if (num === null || num === undefined) return '—';
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

function formatCurrency(amount, currency) {
    if (amount === null || amount === undefined) return '—';
    return currency === 'USD' ? 
        '$' + formatNumber(amount) : 
        formatNumber(amount) + ' UZS';
}

function showNotification(message, type = 'success', autoDismiss = true) {
    // Create a notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '1050';
    notification.style.maxWidth = '350px';
    notification.innerHTML = message + '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>';
    document.body.appendChild(notification);
    
    // Auto-dismiss after 5 seconds if autoDismiss is true
    if (autoDismiss) {
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => document.body.removeChild(notification), 150);
        }, 5000);
    }
    
    // Add click handler for dismiss button
    notification.querySelector('.btn-close').addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => document.body.removeChild(notification), 150);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // Apply styles to the initial form elements
    styleFormElements();

    // Load data from the embedded JSON
    const jsDataElement = document.getElementById('js-data');
    if (!jsDataElement) {
        console.error('Could not find js-data element');
        return;
    }
    const data = JSON.parse(jsDataElement.textContent);
    const agents = data.agents;
    const sellers = data.sellers;
    const purchases = data.ticket_purchases;
    const saleCreateUrl = data.sale_create_url;
    const csrfToken = document.getElementById('csrf_token').value;

    if (!saleCreateUrl || !csrfToken) {
        console.error('Missing sale_create_url or CSRF token');
        return;
    }
    
    // Handle form submission when a SELECT filter changes
    const filterElements = document.querySelectorAll('#filter-form select');
    filterElements.forEach(element => {
        element.addEventListener('change', function() {
            this.form.submit();
        });
    });
    
    // Handle visibility of custom date range inputs
    const dateFilterSelect = document.querySelector('select[name="date_filter"]');
    const customDateRangeDiv = document.getElementById('custom-date-range');
    
    if (dateFilterSelect && customDateRangeDiv) {
        dateFilterSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customDateRangeDiv.classList.remove('d-none');
            } else {
                customDateRangeDiv.classList.add('d-none');
                // Clear custom dates if another option is selected
                document.querySelector('input[name="start_date"]').value = '';
                document.querySelector('input[name="end_date"]').value = '';
                // Submit form if not custom
                this.form.submit(); 
            }
        });
    }
    
    // Excel export functionality
    const exportExcelButton = document.getElementById('exportExcel');
    if (exportExcelButton) {
        exportExcelButton.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = data.excel_export_url || '';
        });
    }
}); 