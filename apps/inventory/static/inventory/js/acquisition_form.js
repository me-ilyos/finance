/**
 * Acquisition Form JavaScript
 * Handles form interactions for simplified acquisition form
 */

console.log('Acquisition form JavaScript is loading...');

document.addEventListener('DOMContentLoaded', function () {
    console.log('DOMContentLoaded fired - starting acquisition form initialization');
    
    // Initialize admin action event listeners
    initializeAdminActions();
    
    // Fix modal select dropdown z-index issues
    fixModalSelectDropdowns();
});

/**
 * Fix modal select dropdown z-index issues
 */
function fixModalSelectDropdowns() {
    const modals = ['#addAcquisitionModal', '#editAcquisitionModal'];
    
    modals.forEach(modalSelector => {
        const modal = document.querySelector(modalSelector);
        if (!modal) return;
        
        const modalElement = new bootstrap.Modal(modal);
        
        // Add event listeners for modal show/hide
        modal.addEventListener('show.bs.modal', function() {
            this.style.zIndex = '1055';
        });
        
        modal.addEventListener('shown.bs.modal', function() {
            const selects = this.querySelectorAll('.form-select');
            selects.forEach(select => {
                select.addEventListener('focus', function() {
                    this.style.zIndex = '1070';
                    this.style.position = 'relative';
                });
                
                select.addEventListener('blur', function() {
                    this.style.zIndex = '1060';
                });
                
                select.addEventListener('click', function() {
                    this.style.position = 'relative';
                    this.style.zIndex = '1070';
                });
            });
        });
        
        modal.addEventListener('hidden.bs.modal', function() {
            const selects = this.querySelectorAll('.form-select');
            selects.forEach(select => {
                select.style.zIndex = '';
                select.style.position = '';
            });
        });
    });
}

/**
 * Initialize Admin Action Event Listeners
 */
function initializeAdminActions() {
    console.log('Initializing admin actions...');
    
    // Use event delegation instead of direct event listeners
    document.body.addEventListener('click', function(event) {
        // Handle edit button clicks
        if (event.target.closest('.edit-acquisition-btn')) {
            event.preventDefault();
            const button = event.target.closest('.edit-acquisition-btn');
            const acquisitionId = button.getAttribute('data-acquisition-id');
            console.log('Edit button clicked for acquisition:', acquisitionId);
            editAcquisition(acquisitionId);
        }
        
        // Handle delete button clicks
        if (event.target.closest('.delete-acquisition-btn')) {
            event.preventDefault();
            const button = event.target.closest('.delete-acquisition-btn');
            const acquisitionId = button.getAttribute('data-acquisition-id');
            console.log('Delete button clicked for acquisition:', acquisitionId);
            deleteAcquisition(acquisitionId);
        }
    });
    
    console.log('Admin actions initialized with event delegation');
}

/**
 * Admin Functions for Acquisition Management
 */

function editAcquisition(acquisitionId) {
    console.log('editAcquisition called with ID:', acquisitionId);
    
    if (!acquisitionId) {
        console.error('No acquisition ID provided');
        showAlert("Xarid ID topilmadi.", 'danger');
        return;
    }
    
    fetch(`/inventory/acquisitions/${acquisitionId}/edit/`)
        .then(response => {
            console.log('Edit response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Edit response data:', data);
            if (data.success) {
                populateEditForm(data.acquisition);
                const modalElement = document.getElementById('editAcquisitionModal');
                if (modalElement) {
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();
                } else {
                    console.error('Edit modal element not found');
                    showAlert("Edit modal topilmadi.", 'danger');
                }
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error in editAcquisition:', error);
            showAlert("Xaridni yuklashda xatolik yuz berdi.", 'danger');
        });
}

function deleteAcquisition(acquisitionId) {
    console.log('deleteAcquisition called with ID:', acquisitionId);
    
    if (!acquisitionId) {
        console.error('No acquisition ID provided for delete');
        showAlert("Xarid ID topilmadi.", 'danger');
        return;
    }
    
    if (confirm("Xaridni o'chirishni tasdiqlaysizmi? Bu amal barcha bog'liq ma'lumotlarni ham o'chiradi.")) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfToken) {
            console.error('CSRF token not found');
            showAlert("CSRF token topilmadi.", 'danger');
            return;
        }
        
        fetch(`/inventory/acquisitions/${acquisitionId}/delete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken.value,
                'Content-Type': 'application/json',
            }
        })
        .then(response => {
            console.log('Delete response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Delete response data:', data);
            if (data.success) {
                showAlert(data.message, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error in deleteAcquisition:', error);
            showAlert("Xaridni o'chirishda xatolik yuz berdi.", 'danger');
        });
    }
}

function populateEditForm(acquisition) {
    const form = document.getElementById('editAcquisitionForm');
    if (!form) return;

    // Set acquisition ID
    document.getElementById('edit_acquisition_id').value = acquisition.id;
    
    // Populate form fields
    form.querySelector('#edit_supplier').value = acquisition.supplier;
    form.querySelector('#edit_acquisition_date').value = acquisition.acquisition_date;
    form.querySelector('#edit_initial_quantity').value = acquisition.initial_quantity;
    form.querySelector('#edit_unit_price').value = acquisition.unit_price;
    form.querySelector('#edit_currency').value = acquisition.currency;
    form.querySelector('#edit_notes').value = acquisition.notes;
    
    // Populate ticket fields
    form.querySelector('#edit_ticket_type').value = acquisition.ticket_type;
    form.querySelector('#edit_ticket_description').value = acquisition.ticket_description;
    form.querySelector('#edit_ticket_departure_date_time').value = acquisition.ticket_departure_date_time;
    form.querySelector('#edit_ticket_arrival_date_time').value = acquisition.ticket_arrival_date_time;
}

function submitEditForm() {
    const form = document.getElementById('editAcquisitionForm');
    const formData = new FormData(form);
    const acquisitionId = document.getElementById('edit_acquisition_id').value;

    fetch(`/inventory/acquisitions/${acquisitionId}/edit/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('editAcquisitionModal'));
            modal.hide();
            showAlert(data.message, 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert("Xaridni yangilashda xatolik yuz berdi.", 'danger');
    });
}

function showAlert(message, type) {
    // Simple alert implementation
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
} 