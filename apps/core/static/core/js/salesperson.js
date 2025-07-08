/**
 * Salesperson List JavaScript
 * Handles salesperson editing and status toggling functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Handle edit salesperson button clicks
    document.querySelectorAll('.edit-salesperson-btn').forEach(button => {
        button.addEventListener('click', function() {
            const id = this.dataset.id;
            const username = this.dataset.username;
            const firstName = this.dataset.firstName;
            const lastName = this.dataset.lastName;
            const email = this.dataset.email;
            const phone = this.dataset.phone;
            const isActive = this.dataset.isActive === 'true';
            
            // Populate edit form
            document.getElementById('edit_salesperson_id').value = id;
            document.getElementById('edit_username').value = username;
            document.getElementById('edit_first_name').value = firstName;
            document.getElementById('edit_last_name').value = lastName;
            document.getElementById('edit_email').value = email;
            document.getElementById('edit_phone_number').value = phone;
            document.getElementById('edit_is_active').checked = isActive;
            
            // Clear password fields for security
            document.getElementById('edit_password').value = '';
            document.getElementById('edit_password_confirm').value = '';
            
            // Set form action to edit endpoint - URL will be set by template
            const editForm = document.getElementById('editSalespersonForm');
            const baseUrl = editForm.dataset.editUrl;
            editForm.action = baseUrl.replace('0', id);
            
            // Show modal
            new bootstrap.Modal(document.getElementById('editSalespersonModal')).show();
        });
    });
    
    // Handle toggle status button clicks
    document.querySelectorAll('.toggle-status-btn').forEach(button => {
        button.addEventListener('click', function() {
            const id = this.dataset.id;
            const action = this.dataset.action;
            const actionText = action === 'activate' ? 'faollashtirish' : 'faolsizlashtirish';
            
            if (confirm(`Haqiqatan ham bu sotuvchini ${actionText}ni xohlaysizmi?`)) {
                // Create and submit form
                const form = document.createElement('form');
                form.method = 'POST';
                
                // Get toggle URL from data attribute on container
                const container = document.querySelector('[data-toggle-url]');
                const toggleUrl = container.dataset.toggleUrl;
                form.action = toggleUrl.replace('0', id);
                
                // Add CSRF token
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
                
                // Add action
                const actionInput = document.createElement('input');
                actionInput.type = 'hidden';
                actionInput.name = 'action';
                actionInput.value = action;
                form.appendChild(actionInput);
                
                document.body.appendChild(form);
                form.submit();
            }
        });
    });
}); 