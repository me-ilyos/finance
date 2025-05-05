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
    const saleCreateUrl = data.sale_create_url; // Get the URL
    const csrfToken = document.getElementById('csrf_token').value;

    if (!saleCreateUrl) {
        console.error('sale_create_url not found in js-data');
        return;
    }
    if (!csrfToken) {
        console.error('CSRF token not found');
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
    
    // Export to Excel
    const exportExcelButton = document.getElementById('exportExcel');
    if (exportExcelButton) {
        exportExcelButton.addEventListener('click', function(e) {
            e.preventDefault();
            exportTableToExcel('salesTable', 'chipta_sotuvlari');
        });
    }
    
    function exportTableToExcel(tableID, filename = '') {
        const table = document.getElementById(tableID);
        if (!table) return;
        let tableHTML = table.outerHTML;
        
        // Convert table to Excel friendly format
        tableHTML = tableHTML.replace(/<img[^>]*>/gi, '');  // Remove images
        
        // Create download link
        let link = document.createElement("a");
        link.download = filename + '.xls';
        
        // Create blob and URL
        let blob = new Blob([tableHTML], {type: 'application/vnd.ms-excel'});
        link.href = URL.createObjectURL(blob);
        
        // Trigger download
        link.click();
        URL.revokeObjectURL(link.href); // Clean up
    }

    // Function to format numbers (shared between initial display and dynamic updates)
    function formatNumber(num) {
        if (num === null || num === undefined) return '—'; // Handle null/undefined
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    }

    // Add new sale row logic
    const addSaleButton = document.getElementById('addSaleBtn');
    if (addSaleButton) {
        addSaleButton.addEventListener('click', function() {
            const tableBody = document.querySelector('#salesTable tbody');
            if (!tableBody) return;
            
            // Remove empty state row if it exists
            const emptyStateRow = tableBody.querySelector('.empty-state');
            if (emptyStateRow) {
                tableBody.innerHTML = '';
            }
            
            // Avoid adding multiple new rows
            if (tableBody.querySelector('.new-sale-row')) {
                return; 
            }

            // Create new editable row
            const newRow = document.createElement('tr');
            newRow.classList.add('new-sale-row');
            
            // Get current date-time in ISO format for the datetime-local input
            const now = new Date();
            const localDatetime = new Date(now.getTime() - (now.getTimezoneOffset() * 60000))
                .toISOString()
                .slice(0, 16);
            
            // Create HTML for the new row
            let rowHtml = `
                <td><span class="badge bg-warning">New</span></td>
                <td><input type="datetime-local" class="form-control form-control-sm" name="sale_date" value="${localDatetime}"></td>
                <td>
                    <select class="form-select form-select-sm" name="customer_type" id="customerTypeSelect">
                        <option value="individual">Individual</option>
                        <option value="agent">Agent</option>
                    </select>
                    <div id="customerNameInput" class="mt-1">
                        <input type="text" class="form-control form-control-sm" name="customer_name" placeholder="Mijoz nomi">
                    </div>
                    <div id="agentSelectDiv" class="mt-1 d-none">
                        <select class="form-select form-select-sm" name="agent">
                            <option value="">Agent tanlang</option>`;
            
            // Add agents dynamically
            agents.forEach(agent => {
                rowHtml += `<option value="${agent.id}">${agent.name}</option>`;
            });
            
            rowHtml += `
                        </select>
                    </div>
                </td>
                <td>
                    <select class="form-select form-select-sm" name="seller">
                        <option value="">Sotuvchi tanlang</option>`;
            
            // Add sellers dynamically
            sellers.forEach(seller => {
                rowHtml += `<option value="${seller.id}">${seller.name}</option>`;
            });
            
            rowHtml += `
                    </select>
                </td>
                <td>
                    <select class="form-select form-select-sm" name="ticket_purchase">
                        <option value="">Xarid tanlang</option>`;
            
            // Add ticket purchases dynamically
            purchases.forEach(purchase => {
                rowHtml += `<option value="${purchase.id}">${purchase.purchase_id} - ${purchase.supplier_name}</option>`;
            });
            
            rowHtml += `
                    </select>
                </td>
                <td><input type="number" class="form-control form-control-sm text-end" name="quantity" min="1" value="1"></td>
                <td><input type="number" class="form-control form-control-sm text-end" name="unit_price" min="0.01" step="0.01" value=""></td>
                <td class="text-end total-price">0.00</td>
                <td class="text-end profit">—</td>
                <td style="display:none;">
                    <select class="form-select form-select-sm" name="currency">
                        <option value="UZS">UZS</option>
                        <option value="USD">USD</option>
                    </select>
                </td>
                <td class="text-center">
                    <button type="button" class="btn btn-sm btn-success save-row">
                        <i class="fas fa-save"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-danger cancel-row">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;
            
            // Set the row HTML
            newRow.innerHTML = rowHtml;
            
            // Insert the new row at the beginning of the table
            if (tableBody.firstChild) {
                tableBody.insertBefore(newRow, tableBody.firstChild);
            } else {
                tableBody.appendChild(newRow);
            }
            
            // Add event listeners for the new row's elements
            setupNewRowListeners(newRow, purchases, saleCreateUrl, csrfToken);
        });
    }
});

// Function to set up listeners for a newly added row
function setupNewRowListeners(newRow, purchases, saleCreateUrl, csrfToken) {
    const customerTypeSelect = newRow.querySelector('#customerTypeSelect');
    const customerNameInput = newRow.querySelector('#customerNameInput');
    const agentSelectDiv = newRow.querySelector('#agentSelectDiv');
    const quantityInput = newRow.querySelector('input[name="quantity"]');
    const priceInput = newRow.querySelector('input[name="unit_price"]');
    const currencySelect = newRow.querySelector('select[name="currency"]');
    const purchaseSelect = newRow.querySelector('select[name="ticket_purchase"]');
    const totalCell = newRow.querySelector('.total-price');
    const profitCell = newRow.querySelector('.profit');
    const saveBtn = newRow.querySelector('.save-row');
    const cancelBtn = newRow.querySelector('.cancel-row');

    // Toggle customer name/agent select
    if (customerTypeSelect) {
        customerTypeSelect.addEventListener('change', function() {
            if (this.value === 'agent') {
                customerNameInput.classList.add('d-none');
                agentSelectDiv.classList.remove('d-none');
            } else {
                customerNameInput.classList.remove('d-none');
                agentSelectDiv.classList.add('d-none');
            }
        });
    }

    // Create purchase prices object for profit calculation
    const purchasePrices = {};
    purchases.forEach(purchase => {
        purchasePrices[purchase.id] = {
            unit_price: purchase.unit_price,
            currency: purchase.currency
        };
    });

    // Function to format numbers (local to this scope if preferred)
    function formatNumber(num) {
        if (num === null || num === undefined) return '—';
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    }

    // Update total and profit calculations
    function updateTotal() {
        const quantity = parseFloat(quantityInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const total = quantity * price;
        const currency = currencySelect.value;
        
        // Format total price
        if (currency === 'USD') {
            totalCell.textContent = '$' + formatNumber(total);
        } else {
            totalCell.textContent = formatNumber(total) + ' UZS';
        }
        
        // Calculate profit if possible
        const purchaseId = purchaseSelect.value;
        if (purchaseId && purchasePrices[purchaseId]) {
            const purchasePrice = purchasePrices[purchaseId];
            
            if (purchasePrice.currency === currency) {
                const profit = (price - purchasePrice.unit_price) * quantity;
                
                // Format profit
                if (currency === 'USD') {
                    profitCell.textContent = '$' + formatNumber(profit);
                } else {
                    profitCell.textContent = formatNumber(profit) + ' UZS';
                }
                
                // Add color based on profit value
                if (profit > 0) {
                    profitCell.classList.add('text-success');
                    profitCell.classList.remove('text-danger');
                } else if (profit < 0) {
                    profitCell.classList.add('text-danger');
                    profitCell.classList.remove('text-success');
                } else {
                    profitCell.classList.remove('text-success', 'text-danger');
                }
            } else {
                profitCell.textContent = '—';
                profitCell.classList.remove('text-success', 'text-danger');
            }
        } else {
            profitCell.textContent = '—';
            profitCell.classList.remove('text-success', 'text-danger');
        }
    }

    quantityInput.addEventListener('input', updateTotal);
    priceInput.addEventListener('input', updateTotal);
    currencySelect.addEventListener('change', updateTotal);
    purchaseSelect.addEventListener('change', updateTotal);

    // Save button click handler
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            // Validate inputs
            const customerType = customerTypeSelect.value;
            const sellerSelect = newRow.querySelector('select[name="seller"]');
            const ticketPurchaseSelect = purchaseSelect;
            const quantity = quantityInput.value;
            const price = priceInput.value;
            const seller = sellerSelect ? sellerSelect.value : null;
            const ticketPurchase = ticketPurchaseSelect ? ticketPurchaseSelect.value : null;

            // Validate customer info
            if (customerType === 'individual') {
                const customerName = newRow.querySelector('input[name="customer_name"]').value;
                if (!customerName) {
                    alert('Please enter customer name');
                    return;
                }
            } else { // agent
                const agentSelect = newRow.querySelector('select[name="agent"]');
                const agent = agentSelect ? agentSelect.value : null;
                if (!agent) {
                    alert('Please select an agent');
                    return;
                }
            }
            
            if (!seller) {
                alert('Please select a seller');
                return;
            }
            
            if (!ticketPurchase) {
                alert('Please select a ticket purchase');
                return;
            }
            
            if (!quantity || parseInt(quantity) < 1) {
                alert('Please enter a valid quantity');
                return;
            }
            
            if (!price || parseFloat(price) <= 0) {
                alert('Please enter a valid price');
                return;
            }
            
            // Create form data
            const formData = new FormData();
            formData.append('customer_type', customerType);
            
            if (customerType === 'individual') {
                formData.append('customer_name', newRow.querySelector('input[name="customer_name"]').value);
            } else {
                const agentSelect = newRow.querySelector('select[name="agent"]');
                formData.append('agent', agentSelect ? agentSelect.value : '');
            }
            
            formData.append('seller', seller);
            formData.append('ticket_purchase', ticketPurchase);
            formData.append('sale_date', newRow.querySelector('input[name="sale_date"]').value);
            formData.append('quantity', quantity);
            formData.append('unit_price', price);
            formData.append('currency', currencySelect.value);
            formData.append('csrfmiddlewaretoken', csrfToken);
            
            // Show loading state
            saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            saveBtn.disabled = true;
            
            // Send AJAX request
            fetch(saleCreateUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update the table dynamically without full page reload
                    const newSale = data.sale;
                    let customerDisplay = newSale.customer;
                    if (customerType === 'agent') {
                        customerDisplay += ' <span class="badge bg-info">Agent</span>';
                    }
                    const profitClass = newSale.profit > 0 ? 'text-success' : newSale.profit < 0 ? 'text-danger' : '';
                    
                    const newRowHTML = `
                        <td>${newSale.sale_id}</td>
                        <td>${newSale.sale_date}</td>
                        <td>${customerDisplay}</td>
                        <td>${newSale.seller}</td>
                        <td>${newSale.ticket_purchase}</td>
                        <td class="text-end">${newSale.quantity}</td>
                        <td class="text-end">${newSale.currency === 'USD' ? '$' : ''}${formatNumber(newSale.unit_price)}${newSale.currency !== 'USD' ? ' UZS' : ''}</td>
                        <td class="text-end">${newSale.currency === 'USD' ? '$' : ''}${formatNumber(newSale.total_price)}${newSale.currency !== 'USD' ? ' UZS' : ''}</td>
                        <td class="text-end ${profitClass}">
                            ${newSale.currency === 'USD' ? '$' : ''}${formatNumber(newSale.profit)}${newSale.currency !== 'USD' ? ' UZS' : ''}
                        </td>
                    `;
                    newRow.innerHTML = newRowHTML;
                    newRow.classList.remove('new-sale-row'); // Mark as saved
                    // TODO: Update totals if necessary, or reload just totals via AJAX
                } else {
                    // Show error
                    alert('Error: ' + (data.errors || 'Failed to save sale'));
                    saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                    saveBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while saving the sale');
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                saveBtn.disabled = false;
            });
        });
    }

    // Cancel button click handler
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            const tableBody = newRow.closest('tbody');
            tableBody.removeChild(newRow);
            
            // If table is now empty, show empty state again
            if (tableBody.children.length === 0) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="9" class="text-center py-4">
                            <div class="empty-state">
                                <i class="fas fa-receipt fa-3x text-muted mb-3"></i>
                                <h5>Hech qanday sotuv topilmadi</h5>
                                <p class="text-muted">
                                    Siz hali hech qanday chipta sotmagansiz. "Yangi Sotuv Qo'shish" tugmasini bosib, birinchi sotuvingizni qo'shing.
                                </p>
                            </div>
                        </td>
                    </tr>
                `;
            }
        });
    }
} 