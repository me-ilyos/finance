/**
 * Acquisition Form JavaScript
 * Handles form interactions for simplified acquisition form
 */

document.addEventListener('DOMContentLoaded', function () {
    const AcquisitionForm = {
        // DOM element references
        currencySelect: document.getElementById('id_currency'),
        paidFromAccountSelect: document.getElementById('id_paid_from_account'),
        modal: document.getElementById('addAcquisitionModal'),

        init: function() {
            this.bindEvents();
            this.filterAccountsByCurrency(); // Initial state
        },

        bindEvents: function() {
            if (this.currencySelect) {
                this.currencySelect.addEventListener('change', () => this.filterAccountsByCurrency());
            }

            if (this.modal) {
                this.modal.addEventListener('shown.bs.modal', () => this.filterAccountsByCurrency());
            }
        },

        filterAccountsByCurrency: function() {
            if (!this.currencySelect || !this.paidFromAccountSelect) {
                return;
            }

            const selectedCurrency = this.currencySelect.value;
            const options = this.paidFromAccountSelect.querySelectorAll('option');

            // Show/hide options based on currency
            options.forEach(option => {
                if (option.value === '') {
                    // Keep empty option visible
                    option.style.display = '';
                    return;
                }

                // Get currency from option text or data attribute
                const optionText = option.textContent;
                const isMatchingCurrency = optionText.includes(`(${selectedCurrency})`);
                
                option.style.display = isMatchingCurrency ? '' : 'none';
            });

            // Reset selection if current selection is not compatible
            const currentOption = this.paidFromAccountSelect.querySelector('option:checked');
            if (currentOption && currentOption.value !== '' && currentOption.style.display === 'none') {
                this.paidFromAccountSelect.value = '';
            }
        }
    };

    // Initialize the form handler
    AcquisitionForm.init();
}); 