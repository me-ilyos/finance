/**
 * Acquisition Form JavaScript
 * Handles currency field visibility and form interactions
 */

document.addEventListener('DOMContentLoaded', function () {
    const AcquisitionForm = {
        // DOM element references
        currencySelect: document.getElementById('id_transaction_currency_modal'),
        priceUzsWrapper: document.getElementById('wrapper_id_unit_price_uzs'),
        priceUsdWrapper: document.getElementById('wrapper_id_unit_price_usd'),
        priceUzsField: document.getElementById('id_unit_price_uzs'),
        priceUsdField: document.getElementById('id_unit_price_usd'),
        modal: document.getElementById('addAcquisitionModal'),

        // Configuration
        config: {
            currencies: {
                UZS: 'UZS',
                USD: 'USD'
            }
        },

        init: function() {
            this.bindEvents();
            this.togglePriceFields(); // Initial state
        },

        bindEvents: function() {
            if (this.currencySelect) {
                this.currencySelect.addEventListener('change', () => this.togglePriceFields());
            }

            if (this.modal) {
                this.modal.addEventListener('shown.bs.modal', () => this.togglePriceFields());
            }
        },

        togglePriceFields: function() {
            if (!this.validateElements()) {
                return;
            }

            const selectedCurrency = this.currencySelect.value;

            // Hide all price fields first
            this.hideAllPriceFields();

            // Show relevant field based on currency
            if (selectedCurrency === this.config.currencies.UZS) {
                this.showUzsField();
            } else if (selectedCurrency === this.config.currencies.USD) {
                this.showUsdField();
            }
        },

        validateElements: function() {
            const requiredElements = [
                this.currencySelect,
                this.priceUzsWrapper,
                this.priceUsdWrapper,
                this.priceUzsField,
                this.priceUsdField
            ];

            return requiredElements.every(element => element !== null);
        },

        hideAllPriceFields: function() {
            // Hide UZS field
            this.priceUzsWrapper.classList.add('initially-hidden');
            this.priceUzsWrapper.style.setProperty('display', 'none', 'important');
            this.priceUzsField.required = false;

            // Hide USD field
            this.priceUsdWrapper.classList.add('initially-hidden');
            this.priceUsdWrapper.style.setProperty('display', 'none', 'important');
            this.priceUsdField.required = false;
        },

        showUzsField: function() {
            this.priceUzsWrapper.classList.remove('initially-hidden');
            this.priceUzsWrapper.style.setProperty('display', 'flex', 'important');
            this.priceUzsField.required = true;
            
            // Clear USD field
            if (this.priceUsdField) {
                this.priceUsdField.value = '';
            }
        },

        showUsdField: function() {
            this.priceUsdWrapper.classList.remove('initially-hidden');
            this.priceUsdWrapper.style.setProperty('display', 'flex', 'important');
            this.priceUsdField.required = true;
            
            // Clear UZS field
            if (this.priceUzsField) {
                this.priceUzsField.value = '';
            }
        }
    };

    // Initialize the form handler
    AcquisitionForm.init();
}); 