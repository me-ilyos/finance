// Force cache reset - version 1.0.1
console.log('New purchases.js loaded successfully - v1.0.1');

document.addEventListener('DOMContentLoaded', function() {
    // --- Get data from the embedded JSON element ---
    const jsDataElement = document.getElementById('js-data');
    if (!jsDataElement) {
        console.error('Could not find js-data element');
        return;
    }
    
    const jsData = JSON.parse(jsDataElement.textContent || '{}');
    const suppliers = jsData.suppliers || [];
    const purchaseCreateUrl = jsData.purchase_create_url;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (!purchaseCreateUrl) {
        console.error('purchase_create_url not found in js-data');
        return;
    }
    if (!csrfToken) {
        console.error('CSRF token not found');
        return;
    }

    // --- Initialize Components ---
    initializeDateRangePicker();
    initializeFilterForm();
    setupExportExcelButton();
    setupAddPurchaseButton();

    // --- Date Range Picker initialization ---
    function initializeDateRangePicker() {
        const daterange = $('#daterange');
        if (!daterange.length || typeof daterange.daterangepicker !== 'function') {
            console.warn('DateRangePicker not available');
            return;
        }

        const startDateInput = $('#start_date_input');
        const endDateInput = $('#end_date_input');

        daterange.daterangepicker({
            autoUpdateInput: false,
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

        // Handle date selection
        daterange.on('apply.daterangepicker', function(ev, picker) {
            $(this).val(picker.startDate.format('YYYY-MM-DD') + ' - ' + picker.endDate.format('YYYY-MM-DD'));
            startDateInput.val(picker.startDate.format('YYYY-MM-DD'));
            endDateInput.val(picker.endDate.format('YYYY-MM-DD'));
            this.form.submit();
        });

        // Handle clear date selection
        daterange.on('cancel.daterangepicker', function(ev, picker) {
            $(this).val('');
            startDateInput.val('');
            endDateInput.val('');
            this.form.submit();
        });
        
        // Set initial values if present
        if (startDateInput.val() && endDateInput.val()) {
            daterange.val(startDateInput.val() + ' - ' + endDateInput.val());
        }
    }

    // --- Auto submit filter form on change ---
    function initializeFilterForm() {
        const filterForm = document.getElementById('filter-form');
        if (!filterForm) return;

        const filterSelects = filterForm.querySelectorAll('select[name="supplier"], select[name="currency"], select[name="sort_by"]');
        filterSelects.forEach(select => {
            select.addEventListener('change', () => filterForm.submit());
        });
    }

    // --- Format numbers with commas and currency ---
    function formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }

    function formatCurrency(amount, currency) {
        const formatter = new Intl.NumberFormat(undefined, { 
            minimumFractionDigits: 2, 
            maximumFractionDigits: 2 
        });
        
        return currency === 'USD' 
            ? '$' + formatter.format(amount) 
            : formatter.format(amount) + ' UZS';
    }

    // --- Setup Add Purchase Button ---
    function setupAddPurchaseButton() {
        const addPurchaseBtn = document.getElementById('addPurchaseBtn');
        const tableBody = document.querySelector('#purchasesTable tbody');
        
        if (!addPurchaseBtn || !tableBody) {
            console.warn('Add Purchase button or table body not found');
            return;
        }

        addPurchaseBtn.addEventListener('click', function() {
            // Remove empty state row if it exists
            const emptyStateRow = tableBody.querySelector('.empty-state-row');
            if (emptyStateRow) {
                tableBody.innerHTML = '';
            }
            
            // Avoid adding multiple new rows
            if (tableBody.querySelector('.new-purchase-row')) {
                return;
            }
            
            // Current datetime for the datetime-local input
            const now = new Date();
            const localDatetime = new Date(now.getTime() - (now.getTimezoneOffset() * 60000))
                .toISOString()
                .slice(0, 16);
            
            // Create supplier options HTML
            const supplierOptions = suppliers.map(s => 
                `<option value="${s.id}">${s.name}</option>`
            ).join('');
            
            // Create new row
            const newRow = document.createElement('tr');
            newRow.className = 'new-purchase-row align-middle';
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
                <td class="text-end">0</td>
                <td class="text-end">1</td>
                <td class="text-end">
                    <input type="number" class="form-control form-control-sm text-end" name="unit_price" min="0.01" step="0.01" required placeholder="0.00" style="min-width: 100px;">
                    <select class="form-select form-select-sm mt-1" name="currency">
                        <option value="UZS" selected>UZS</option>
                        <option value="USD">USD</option>
                    </select>
                </td>
                <td class="text-end calculated-total-price">0.00 UZS</td>
                <td>
                    <button type="button" class="btn btn-sm btn-success save-btn" title="Saqlash">
                        <i class="fas fa-save"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-danger cancel-btn" title="Bekor qilish">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;
            
            // Insert at the beginning of the table
            if (tableBody.firstChild) {
                tableBody.insertBefore(newRow, tableBody.firstChild);
            } else {
                tableBody.appendChild(newRow);
            }
            
            // Add event listeners to the new row
            setupRowListeners(newRow);
        });
    }

    // --- Setup listeners for a newly added row ---
    function setupRowListeners(row) {
        const quantityInput = row.querySelector('input[name="quantity"]');
        const priceInput = row.querySelector('input[name="unit_price"]');
        const currencySelect = row.querySelector('select[name="currency"]');
        const totalCell = row.querySelector('.calculated-total-price');
        const saveBtn = row.querySelector('.save-btn');
        const cancelBtn = row.querySelector('.cancel-btn');
        
        // Update the total price on input changes
        function updateTotal() {
            const quantity = parseFloat(quantityInput.value) || 0;
            const price = parseFloat(priceInput.value) || 0;
            const total = quantity * price;
            const currency = currencySelect.value;
            
            totalCell.textContent = formatCurrency(total, currency);
            
            // Update remaining quantity cell
            const remainingCell = row.querySelector('td:nth-child(6)');
            if (remainingCell) remainingCell.textContent = formatNumber(quantity);
        }
        
        quantityInput.addEventListener('input', updateTotal);
        priceInput.addEventListener('input', updateTotal);
        currencySelect.addEventListener('change', updateTotal);
        
        // Save button
        saveBtn.addEventListener('click', function() {
            // Basic validation
            const supplier = row.querySelector('select[name="supplier"]').value;
            const date = row.querySelector('input[name="purchase_date"]').value;
            const quantity = quantityInput.value;
            const price = priceInput.value;
            
            if (!date || !supplier || !quantity || quantity < 1 || !price || price <= 0) {
                showAlert('Iltimos, barcha maydonlarni to\'ldiring.', 'warning');
                return;
            }
            
            // Create form data
            const formData = new FormData();
            formData.append('supplier', supplier);
            formData.append('purchase_date', date);
            formData.append('quantity', quantity);
            formData.append('unit_price', price);
            formData.append('currency', currencySelect.value);
            formData.append('csrfmiddlewaretoken', csrfToken);
            
            // Show loading state
            const originalBtnHtml = saveBtn.innerHTML;
            saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            saveBtn.disabled = true;
            
            // Send AJAX request
            fetch(purchaseCreateUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && data.purchase) {
                    // Create saved row HTML
                    const savedRowHTML = `
                        <td>${data.purchase.purchase_id}</td>
                        <td>${data.purchase.purchase_date}</td>
                        <td>${data.purchase.supplier}</td>
                        <td class="text-end">${formatNumber(data.purchase.quantity)}</td>
                        <td class="text-end">0</td>
                        <td class="text-end">${formatNumber(data.purchase.quantity)}</td>
                        <td class="text-end">${formatCurrency(data.purchase.unit_price, data.purchase.currency)}</td>
                        <td class="text-end">${formatCurrency(data.purchase.total_price, data.purchase.currency)}</td>
                    `;
                    
                    // Replace editable row with saved data
                    row.innerHTML = savedRowHTML;
                    row.classList.remove('new-purchase-row');
                    showAlert('Xarid muvaffaqiyatli saqlandi!', 'success');
                } else {
                    showAlert('Xatolik: ' + (data.errors || 'Saqlashda xatolik yuz berdi.'), 'danger');
                    saveBtn.innerHTML = originalBtnHtml;
                    saveBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Server bilan bog\'lanishda xatolik.', 'danger');
                saveBtn.innerHTML = originalBtnHtml;
                saveBtn.disabled = false;
            });
        });
        
        // Cancel button
        cancelBtn.addEventListener('click', function() {
            const tableBody = row.closest('tbody');
            tableBody.removeChild(row);
            
            // If table is now empty, show empty state again
            if (tableBody.children.length === 0) {
                tableBody.innerHTML = `<tr class="empty-state-row">
                    <td colspan="8" class="text-center py-4">
                        <div class="empty-state">
                            <i class="fas fa-shopping-cart fa-3x text-muted mb-3"></i>
                            <h5>Hech qanday xarid topilmadi</h5>
                            <p class="text-muted">
                                Siz hali hech qanday chipta xarid qilmagansiz. "Yangi Xarid Qo'shish" tugmasini bosib, birinchi xaridingizni qo'shing.
                            </p>
                        </div>
                    </td>
                </tr>`;
            }
        });
    }

    // --- Setup Export Excel Button ---
    function setupExportExcelButton() {
        const exportBtn = document.getElementById('exportExcel');
        if (exportBtn) {
            exportBtn.addEventListener('click', function(e) {
                e.preventDefault();
                showAlert('Excel eksport qilish hozircha mavjud emas.', 'info');
            });
        }
    }

    // --- Show alert messages ---
    function showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alert-container');
        if (!alertContainer) {
            alert(message);
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        alertContainer.appendChild(wrapper);

        // Auto-dismiss non-error alerts
        if (type !== 'danger') {
            setTimeout(() => {
                const alertElement = wrapper.querySelector('.alert');
                if (alertElement) {
                    const bsAlert = bootstrap.Alert.getOrCreateInstance(alertElement);
                    if (bsAlert) bsAlert.close();
                }
            }, 5000);
        }
    }
}); 