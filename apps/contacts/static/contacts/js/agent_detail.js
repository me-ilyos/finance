// Agent Detail Page JavaScript - Simplified
document.addEventListener('DOMContentLoaded', function() {
    const currencySelect = document.getElementById('id_currency');
    const accountSelect = document.getElementById('id_paid_to_account');

    if (!currencySelect || !accountSelect) {
        console.warn('Payment form elements not found');
        return;
    }

    // Filter accounts by currency when currency changes
    currencySelect.addEventListener('change', function() {
        const selectedCurrency = this.value;
        const options = accountSelect.querySelectorAll('option');
        
        options.forEach(option => {
            if (option.value === '') {
                option.style.display = 'block';
                return;
            }
            
            const optionText = option.textContent;
            if (optionText.includes(`(${selectedCurrency})`)) {
                option.style.display = 'block';
            } else {
                option.style.display = 'none';
            }
        });
        
        // Reset account selection if current selection doesn't match currency
        const currentSelection = accountSelect.value;
        if (currentSelection) {
            const currentOption = accountSelect.querySelector(`option[value="${currentSelection}"]`);
            if (currentOption && currentOption.style.display === 'none') {
                accountSelect.value = '';
            }
        }
    });

    // Initialize form state
    if (currencySelect.value) {
        currencySelect.dispatchEvent(new Event('change'));
    }
}); 