// Agent Detail Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const paymentForm = document.getElementById('paymentForm');
    const relatedSaleSelect = document.getElementById('id_related_sale');
    const amountUzsInput = document.getElementById('id_amount_paid_uzs');
    const amountUsdInput = document.getElementById('id_amount_paid_usd');
    const paidToAccountSelect = document.getElementById('id_paid_to_account');

    if (!paymentForm || !relatedSaleSelect || !amountUzsInput || !amountUsdInput || !paidToAccountSelect) {
        console.warn('Payment form elements not found');
        return;
    }

    // Event listeners
    relatedSaleSelect.addEventListener('change', updatePaymentFormForSale);
    amountUzsInput.addEventListener('input', handleAmountChange);
    amountUsdInput.addEventListener('input', handleAmountChange);

    function updatePaymentFormForSale() {
        // Reset amounts
        amountUzsInput.value = '0';
        amountUsdInput.value = '0';
        amountUzsInput.disabled = true;
        amountUsdInput.disabled = true;
        paidToAccountSelect.disabled = false;

        const selectedOption = relatedSaleSelect.options[relatedSaleSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value) {
            filterAccountOptionsByCurrency(null);
            return;
        }

        const saleText = selectedOption.text;
        const balanceMatch = saleText.match(/Balans: ([\d,\.]+) (UZS|USD)/);
        
        if (!balanceMatch) {
            filterAccountOptionsByCurrency(null);
            return;
        }

        const balance = parseFloat(balanceMatch[1].replace(/,/g, ''));
        const currency = balanceMatch[2];

        if (currency === 'UZS') {
            amountUzsInput.value = balance.toFixed(0);
            amountUzsInput.max = balance.toFixed(0);
            amountUzsInput.disabled = false;
            amountUsdInput.value = '';
            amountUsdInput.disabled = true;
        } else if (currency === 'USD') {
            amountUsdInput.value = balance.toFixed(2);
            amountUsdInput.max = balance.toFixed(2);
            amountUsdInput.disabled = false;
            amountUzsInput.value = '';
            amountUzsInput.disabled = true;
        }
        
        filterAccountOptionsByCurrency(currency);
    }

    function handleAmountChange(event) {
        const changedInput = event.target;
        const otherInput = changedInput === amountUzsInput ? amountUsdInput : amountUzsInput;
        const currency = changedInput === amountUzsInput ? 'UZS' : 'USD';

        if (parseFloat(changedInput.value) > 0) {
            otherInput.value = '0';
            otherInput.disabled = true;
            filterAccountOptionsByCurrency(currency);
        } else {
            otherInput.disabled = false;
            filterAccountOptionsByCurrency(null);
        }
    }

    function filterAccountOptionsByCurrency(currency) {
        const options = paidToAccountSelect.options;
        
        for (let i = 0; i < options.length; i++) {
            const option = options[i];
            if (option.value === '') {
                option.style.display = '';
                continue;
            }

            const optionText = option.text;
            const isCurrencyMatch = currency ? optionText.includes(`(${currency})`) : true;
            option.style.display = isCurrencyMatch ? '' : 'none';
        }

        // Reset selection if current selection is hidden
        if (paidToAccountSelect.selectedOptions[0] && 
            paidToAccountSelect.selectedOptions[0].style.display === 'none') {
            paidToAccountSelect.value = '';
        }
    }

    // Initialize form state
    updatePaymentFormForSale();
}); 