/**
 * Expenditure Form JavaScript
 * Handles modal display, form validation, and dynamic account filtering
 */

document.addEventListener('DOMContentLoaded', function () {
    // Handle modal display if form has errors on page load
    const expenditureFormErrors = document.querySelector('#expenditureModalForm .invalid-feedback, #expenditureModalForm .alert-danger');
    const addExpenditureModalElement = document.getElementById('addExpenditureModal');

    if (expenditureFormErrors && addExpenditureModalElement) {
        var addExpenditureModalInstance = new bootstrap.Modal(addExpenditureModalElement);
        addExpenditureModalInstance.show();
    }

    // Dynamic filtering for paid_from_account based on currency selection in modal
    const currencySelectModal = document.getElementById('id_currency');
    const paidFromAccountSelectModal = document.getElementById('id_paid_from_account');
    let allAccounts = [];

    // Store all account options initially if the select element exists
    if (paidFromAccountSelectModal) {
        Array.from(paidFromAccountSelectModal.options).forEach(option => {
            if (option.value) { // Exclude the empty "Select Account" option
                allAccounts.push({
                    value: option.value,
                    text: option.text,
                    currency: option.text.includes('USD') ? 'USD' : (option.text.includes('UZS') ? 'UZS' : '')
                });
            }
        });
    }
    
    function filterAccountsByCurrency() {
        if (!currencySelectModal || !paidFromAccountSelectModal || allAccounts.length === 0) return;

        const selectedCurrency = currencySelectModal.value;
        const currentAccountValue = paidFromAccountSelectModal.value;

        // Clear existing options except the first one (placeholder)
        while (paidFromAccountSelectModal.options.length > 1) {
            paidFromAccountSelectModal.remove(1);
        }
        
        allAccounts.forEach(account => {
            // Filter accounts by currency match
            if (selectedCurrency === "" || account.text.includes(selectedCurrency)) {
                 const option = document.createElement('option');
                 option.value = account.value;
                 option.text = account.text;
                 paidFromAccountSelectModal.appendChild(option);
            }
        });

        // Try to reselect previous value if it's still valid
        if (Array.from(paidFromAccountSelectModal.options).some(opt => opt.value === currentAccountValue)) {
            paidFromAccountSelectModal.value = currentAccountValue;
        }
    }

    // Event listeners
    if (currencySelectModal) {
        currencySelectModal.addEventListener('change', filterAccountsByCurrency);
        // Initial filter call in case a currency is pre-selected
        filterAccountsByCurrency();
    }
    
    // When modal is shown, re-trigger the filter if necessary
    if (addExpenditureModalElement) {
        addExpenditureModalElement.addEventListener('shown.bs.modal', function () {
            if (currencySelectModal) filterAccountsByCurrency();
        });
    }
}); 