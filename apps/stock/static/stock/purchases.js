document.addEventListener('DOMContentLoaded', function() {
    // --- Globals ---
    const jsDataElement = document.getElementById('js-data');
    const jsData = jsDataElement ? JSON.parse(jsDataElement.textContent) : {};
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value; // Get CSRF token

    // --- Initialize Components ---
    initializeDateRangePicker('#daterange', '#start_date_input', '#end_date_input');
    initializeFilterFormSubmission(); // Optional: Auto-submit on filter change

    // --- Event Listeners ---
    setupAddPurchaseButton(jsData);
    setupExportExcelButton(); // Placeholder for export functionality

});

/**
 * Initializes the date range picker component.
 */
function initializeDateRangePicker(selector, startDateSelector, endDateSelector, callback) {
    if (typeof $(selector).daterangepicker !== 'function') {
        console.warn('DateRangePicker is not loaded.');
        return;
    }
    
    const startDateInput = $(startDateSelector);
    const endDateInput = $(endDateSelector);

    $(selector).daterangepicker({
        autoUpdateInput: false, // Don't automatically update the input field
        locale: {
            cancelLabel: 'Tozalash',
            applyLabel: 'Qo\'llash',
            format: 'YYYY-MM-DD'
        },
        ranges: {
           'Bugun': [moment(), moment()],
           'Kecha': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
           'Oxirgi 7 kun': [moment().subtract(6, 'days'), moment()],
           'Oxirgi 30 kun': [moment().subtract(29, 'days'), moment()],
           'Shu oy': [moment().startOf('month'), moment().endOf('month')],
           'O\'tgan oy': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        }
    });

    // Update input field when range is applied
    $(selector).on('apply.daterangepicker', function(ev, picker) {
        $(this).val(picker.startDate.format('YYYY-MM-DD') + ' - ' + picker.endDate.format('YYYY-MM-DD'));
        startDateInput.val(picker.startDate.format('YYYY-MM-DD'));
        endDateInput.val(picker.endDate.format('YYYY-MM-DD'));
        if (callback && typeof callback === 'function') {
            callback(picker.startDate, picker.endDate);
        }
         // Automatically submit form when date is selected
         this.form.submit();
    });

    // Clear input field on cancel
    $(selector).on('cancel.daterangepicker', function(ev, picker) {
        $(this).val('');
        startDateInput.val('');
        endDateInput.val('');
         // Automatically submit form when date is cleared
         this.form.submit();
    });
    
    // Set initial value if start/end dates are present
    const initialStartDate = startDateInput.val();
    const initialEndDate = endDateInput.val();
    if (initialStartDate && initialEndDate) {
        $(selector).val(initialStartDate + ' - ' + initialEndDate);
    }
}

/**
 * Adds event listeners to filter dropdowns to submit the form on change.
 * (Optional - enable if you don't want an explicit Filter button)
 */
function initializeFilterFormSubmission() {
    const filterForm = document.getElementById('filter-form'); // Ensure your form has id="filter-form"
    if (!filterForm) return;

    const filterSelects = filterForm.querySelectorAll('select[name="supplier"], select[name="currency"], select[name="sort_by"]');
    filterSelects.forEach(element => {
        element.addEventListener('change', function() {
            filterForm.submit();
        });
    });
    
    // Note: Date range picker handles its own submission in initializeDateRangePicker
}


/**
 * Sets up the event listener for the "Add Purchase" button.
 */
function setupAddPurchaseButton(jsData) {
    const addPurchaseBtn = document.getElementById('addPurchaseBtn');
    const tableBody = document.querySelector('#purchasesTable tbody');

    if (!addPurchaseBtn || !tableBody) {
        console.warn('Add Purchase button or table body not found.');
        return;
    }
    if (!jsData.suppliers || !jsData.purchase_create_url) {
         console.error('Supplier data or purchase create URL missing from jsData.');
         return;
    }

    addPurchaseBtn.addEventListener('click', function() {
        // Remove empty state row if it exists
        const emptyStateRow = tableBody.querySelector('.empty-state-row'); // Add class="empty-state-row" to the empty row tr
        if (emptyStateRow) {
            tableBody.innerHTML = '';
        }

        // Check if a new row already exists
        if (tableBody.querySelector('.new-purchase-row')) {
            // Optionally focus the first input of the existing new row
            tableBody.querySelector('.new-purchase-row input[type="datetime-local"]').focus();
            return; 
        }

        // Create new editable row
        const newRow = tableBody.insertRow(0); // Insert at the top
        newRow.classList.add('new-purchase-row', 'align-middle'); // Add classes

        // Get current date-time in ISO format for the datetime-local input
        const now = new Date();
        const localDatetime = new Date(now.getTime() - (now.getTimezoneOffset() * 60000))
            .toISOString()
            .slice(0, 16);

        // Supplier options HTML
        const supplierOptions = jsData.suppliers.map(s => 
            `<option value="${s.id}">${s.name}</option>`
        ).join('');

        newRow.innerHTML = `
            <td><span class="badge bg-warning">Yangi</span></td>
            <td><input type="datetime-local" class="form-control form-control-sm" name="purchase_date" value="${localDatetime}" style="min-width: 160px;"></td>
            <td>
                <select class="form-select form-select-sm" name="supplier" required>
                    <option value="" disabled selected>Tanlang...</option>
                    ${supplierOptions}
                </select>
            </td>
            <td class="text-end"><input type="number" class="form-control form-control-sm text-end" name="quantity" min="1" value="1" required style="min-width: 70px;"></td>
            <td class="text-end new-quantity-sold">0</td>
            <td class="text-end new-quantity-remaining">1</td>
            <td class="text-end">
                <input type="number" class="form-control form-control-sm text-end" name="unit_price" min="0.01" step="0.01" value="" required placeholder="0.00" style="min-width: 100px;">
                <select class="form-select form-select-sm mt-1" name="currency">
                    <option value="UZS">UZS</option>
                    <option value="USD">USD</option>
                </select>
            </td>
            <td class="text-end calculated-total-price">0.00 UZS</td>
            <td class="text-end actions">
                <button type="button" class="btn btn-sm btn-success save-row" title="Saqlash">
                    <i class="fas fa-save"></i>
                </button>
                <button type="button" class="btn btn-sm btn-danger cancel-row ms-1" title="Bekor qilish">
                    <i class="fas fa-times"></i>
                </button>
            </td>
        `;

        // Add event listeners for the new row
        setupNewRowEventListeners(newRow);
        
        // Focus the first input
        newRow.querySelector('input[name="purchase_date"]').focus();
    });
}

/**
 * Adds event listeners (update total, save, cancel) to a newly added row.
 * @param {HTMLTableRowElement} newRow The newly created table row.
 */
function setupNewRowEventListeners(newRow) {
    const quantityInput = newRow.querySelector('input[name="quantity"]');
    const priceInput = newRow.querySelector('input[name="unit_price"]');
    const currencySelect = newRow.querySelector('select[name="currency"]');
    const totalCell = newRow.querySelector('.calculated-total-price');
    const quantityRemainingCell = newRow.querySelector('.new-quantity-remaining');
    const saveBtn = newRow.querySelector('.save-row');
    const cancelBtn = newRow.querySelector('.cancel-row');

    const updateTotal = () => {
        const quantity = parseFloat(quantityInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const total = quantity * price;
        const currency = currencySelect.value;
        
        const formatter = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        if (currency === 'USD') {
            totalCell.textContent = '$' + formatter.format(total);
        } else {
            totalCell.textContent = formatter.format(total) + ' UZS';
        }
        // Update remaining quantity display
        quantityRemainingCell.textContent = new Intl.NumberFormat().format(quantity);
    };

    quantityInput.addEventListener('input', updateTotal);
    priceInput.addEventListener('input', updateTotal);
    currencySelect.addEventListener('change', updateTotal);

    // --- Save Button ---
    saveBtn.addEventListener('click', function() {
        // Basic Frontend Validation
        const supplier = newRow.querySelector('select[name="supplier"]').value;
        const quantity = quantityInput.value;
        const price = priceInput.value;
        const date = newRow.querySelector('input[name="purchase_date"]').value;
        
        if (!date || !supplier || !quantity || parseFloat(quantity) < 1 || !price || parseFloat(price) <= 0) {
             showAlert('Iltimos, barcha kerakli maydonlarni to\'ldiring.', 'warning');
            // Highlight invalid fields (optional)
             [date, supplier, quantity, price].forEach(val => {
                 const input = newRow.querySelector(`[name="${val === date ? 'purchase_date' : val === supplier ? 'supplier' : val === quantity ? 'quantity' : 'unit_price'}"]`);
                 if(input && (!input.value || (input.type === 'number' && parseFloat(input.value) <= (input.name === 'quantity' ? 0 : 0)))) {
                    input.classList.add('is-invalid');
                 } else if (input) {
                    input.classList.remove('is-invalid');
                 }
             });
            return;
        }
        // Remove validation classes if all ok
        newRow.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

        // Create form data
        const formData = new FormData();
        formData.append('supplier', supplier);
        formData.append('purchase_date', date);
        formData.append('quantity', quantity);
        formData.append('unit_price', price);
        formData.append('currency', currencySelect.value);
        formData.append('csrfmiddlewaretoken', csrfToken); // Use token from top

        // Show loading state
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        saveBtn.disabled = true;
        cancelBtn.disabled = true;

        // Send AJAX request
        fetch(jsData.purchase_create_url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.purchase) {
                // Replace editable row with regular row
                const savedRow = createSavedRow(data.purchase);
                newRow.parentNode.replaceChild(savedRow, newRow);
                showAlert('Xarid muvaffaqiyatli saqlandi!', 'success');
            } else {
                // Show error
                showAlert(`Xatolik: ${data.errors || 'Saqlashda xatolik.'}`, 'danger');
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                saveBtn.disabled = false;
                cancelBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Server bilan bog\'lanishda xatolik.', 'danger');
            saveBtn.innerHTML = '<i class="fas fa-save"></i>';
            saveBtn.disabled = false;
            cancelBtn.disabled = false;
        });
    });

    // --- Cancel Button ---
    cancelBtn.addEventListener('click', function() {
        newRow.remove();
        // If table is now empty, potentially show empty state again (needs check)
        const tableBody = document.querySelector('#purchasesTable tbody');
        if (tableBody && tableBody.children.length === 0) {
            // You might need to fetch the empty state HTML or have it stored
             tableBody.innerHTML = `<tr class="empty-state-row"><td colspan="10" class="text-center py-4">Xaridlar mavjud emas.</td></tr>`; 
        }
    });
}


/**
 * Creates a static table row from saved purchase data.
 * @param {object} purchaseData Data returned from the server after saving.
 * @returns {HTMLTableRowElement} The created table row.
 */
function createSavedRow(purchaseData) {
    const purchaseRow = document.createElement('tr');
    purchaseRow.classList.add('align-middle'); // Optional: ensure vertical alignment

    const formatCurrency = (value, currency) => {
         const formatter = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
         return currency === 'USD' ? `$${formatter.format(value)}` : `${formatter.format(value)} UZS`;
    };
     const formatNumber = (value) => {
         return new Intl.NumberFormat().format(value);
     };


    purchaseRow.innerHTML = `
        <td>${purchaseData.purchase_id}</td>
        <td>${purchaseData.purchase_date}</td> {# Format date as needed server-side or here #}
        <td>${purchaseData.supplier}</td>
        <td class="text-end">${formatNumber(purchaseData.quantity)}</td>
        <td class="text-end">0</td> {# Starts with 0 sold #}
        <td class="text-end">${formatNumber(purchaseData.quantity)}</td> {# Remaining = quantity #}
        <td class="text-end">${formatCurrency(purchaseData.unit_price, purchaseData.currency)}</td>
        <td class="text-end">${formatCurrency(purchaseData.total_price, purchaseData.currency)}</td>
    `;
    return purchaseRow;
}

/**
 * Sets up the event listener for the Export to Excel button (placeholder).
 */
function setupExportExcelButton() {
    const exportBtn = document.getElementById('exportExcel');
    if (exportBtn) {
        exportBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // TODO: Implement Excel export functionality
            // This usually involves constructing a URL with current filters
            // and redirecting or triggering a download.
            // Example: window.location.href = `/stock/purchases/export/?${getCurrentFilterParams()}`;
             showAlert('Excel eksport qilish hozircha mavjud emas.', 'info');
        });
    }
}

/**
 * Utility function to show Bootstrap alerts dynamically.
 * @param {string} message The alert message.
 * @param {string} type Bootstrap alert type (e.g., 'success', 'danger', 'warning', 'info').
 */
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container'); // Need an element with id="alert-container" in base.html or template
     if (!alertContainer) {
        console.error('Alert container not found. Please add `<div id="alert-container" class="position-fixed top-0 end-0 p-3" style="z-index: 1056"></div>` to your base template.');
        alert(message); // Fallback to simple alert
        return;
    }

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    alertContainer.append(wrapper);

    // Auto-dismiss after 5 seconds
     const alertInstance = new bootstrap.Alert(wrapper.querySelector('.alert'));
     setTimeout(() => {
        alertInstance.close();
     }, 5000);
} 