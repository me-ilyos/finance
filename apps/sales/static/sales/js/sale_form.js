/**
 * Sale Form JavaScript - Version 2.0
 * Handles modal form interactions, field dependencies, and AJAX calls
 * Updated: Fixed financial accounts loading
 */

document.addEventListener('DOMContentLoaded', function () {
    console.log('Sale Form JavaScript v2.0 loaded - Financial accounts fix applied');
    
    // Form elements
    const agentSelectModal = document.getElementById('id_agent');
    const clientFullNameModal = document.getElementById('id_client_full_name');
    const clientIDNumberModal = document.getElementById('id_client_id_number');
    const relatedAcquisitionSelectModal = document.getElementById('id_related_acquisition');
    const paidToAccountSelectModal = document.getElementById('id_paid_to_account');
    const paidToAccountWrapper = document.getElementById('wrapper_id_paid_to_account');
    const paidToAccountLabelModal = document.querySelector("label[for='id_paid_to_account']");

    /**
     * Fix modal select dropdown z-index issues
     */
    function fixSelectDropdownZIndex() {
        const modalSelects = document.querySelectorAll('#addSaleModal .form-select');
        modalSelects.forEach(select => {
            select.addEventListener('focus', function() {
                this.style.zIndex = '1070';
            });
            
            select.addEventListener('blur', function() {
                this.style.zIndex = '1060';
            });
            
            // Fix for Bootstrap 5 select styling
            select.addEventListener('click', function() {
                this.style.position = 'relative';
                this.style.zIndex = '1070';
            });
        });
    }

    /**
     * Toggle client/agent fields and payment requirements based on agent selection
     */
    function toggleClientAgentFields() {
        if (!agentSelectModal || !clientFullNameModal || !clientIDNumberModal || 
            !paidToAccountWrapper || !paidToAccountLabelModal) {
            return;
        }

        if (agentSelectModal.value) {
            // Agent selected - disable client fields, disable payment account (creates debt)
            clientFullNameModal.value = '';
            clientIDNumberModal.value = '';
            clientFullNameModal.disabled = true;
            clientIDNumberModal.disabled = true;
            
            // Agent sales create debt - no payment account allowed
            paidToAccountSelectModal.value = '';
            paidToAccountSelectModal.disabled = true;
            
            // Use Bootstrap classes to hide while maintaining layout structure
            paidToAccountWrapper.classList.add('d-none');
        } else {
            // No agent - enable client fields, require payment account
            clientFullNameModal.disabled = false;
            clientIDNumberModal.disabled = false;
            
            // Customer sales require immediate payment
            paidToAccountSelectModal.disabled = false;
            
            // Use Bootstrap classes to show while maintaining layout structure
            paidToAccountWrapper.classList.remove('d-none');
        }
    }

    /**
     * Update payment account options based on acquisition currency
     */
    async function updatePaymentAccountOptions() {
        console.log('updatePaymentAccountOptions called');
        
        if (!relatedAcquisitionSelectModal || !paidToAccountSelectModal) {
            console.log('Required elements not found');
            return;
        }

        const acquisitionId = relatedAcquisitionSelectModal.value;
        paidToAccountSelectModal.innerHTML = '<option value="">---------</option>';

        if (!acquisitionId) {
            paidToAccountSelectModal.disabled = true;
            return;
        }

        // If agent is selected, keep payment account disabled
        if (agentSelectModal && agentSelectModal.value) {
            paidToAccountSelectModal.disabled = true;
            return;
        }

        paidToAccountSelectModal.disabled = false;

        try {
            // Get the acquisition to find its currency
            const acquisitionSelect = document.getElementById('id_related_acquisition');
            
            if (!acquisitionSelect) {
                console.log('Acquisition select element not found');
                return;
            }
            
            const selectedOption = acquisitionSelect.options[acquisitionSelect.selectedIndex];
            
            if (!selectedOption || !selectedOption.textContent) {
                console.log('No acquisition selected or no text content');
                return;
            }
            
            // Better currency detection from acquisition text
            const text = selectedOption.textContent;
            console.log('Acquisition text:', text);
            
            let currency = 'USD'; // Default
            if (text.includes('UZS')) {
                currency = 'UZS';
            } else if (text.includes('USD') || text.includes('$')) {
                currency = 'USD';
            }
            
            console.log('Detected currency:', currency);
            
            const url = `/sales/get-accounts/?currency=${currency}`;
            console.log('Fetching URL:', url);
            const response = await fetch(url);
            
            if (!response.ok) {
                paidToAccountSelectModal.innerHTML = '<option value="">Hisoblar yuklanmadi</option>';
                return;
            }
            
            const data = await response.json();
            console.log('Response data:', data);
            
            if (data.error) {
                console.log('API error:', data.error);
                paidToAccountSelectModal.innerHTML = '<option value="">Xatolik: ' + data.error + '</option>';
                return;
            }

            if (!data.accounts || data.accounts.length === 0) {
                console.log('No accounts found for currency:', currency);
                // Try loading all accounts as fallback
                const fallbackUrl = `/sales/get-accounts/?currency=UZS`;
                console.log('Trying fallback URL:', fallbackUrl);
                const fallbackResponse = await fetch(fallbackUrl);
                const fallbackData = await fallbackResponse.json();
                
                if (fallbackData.accounts && fallbackData.accounts.length > 0) {
                    console.log('Found fallback accounts:', fallbackData.accounts.length);
                    fallbackData.accounts.forEach(account => {
                        const option = document.createElement('option');
                        option.value = account.id;
                        option.textContent = account.name;
                        paidToAccountSelectModal.appendChild(option);
                    });
                } else {
                    paidToAccountSelectModal.innerHTML = '<option value="">Mos hisob topilmadi</option>';
                }
            } else {
                console.log('Found accounts:', data.accounts.length);
                data.accounts.forEach(account => {
                    const option = document.createElement('option');
                    option.value = account.id;
                    option.textContent = account.name;
                    paidToAccountSelectModal.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading accounts:', error);
            paidToAccountSelectModal.innerHTML = '<option value="">Skript xatosi</option>';
        }
    }

    /**
     * Initialize modal when shown
     */
    function initializeModal() {
        console.log('initializeModal called');
        
        // Ensure proper initial alignment
        if (paidToAccountWrapper) {
            paidToAccountWrapper.classList.remove('d-none');
            paidToAccountWrapper.style.display = '';
        }
        
        if (agentSelectModal) toggleClientAgentFields();
        if (relatedAcquisitionSelectModal && relatedAcquisitionSelectModal.value) {
            console.log('Calling updatePaymentAccountOptions from initializeModal');
            updatePaymentAccountOptions();
        }
        // Fix z-index issues
        fixSelectDropdownZIndex();
    }

    /**
     * Show modal if form has errors on page load
     */
    function showModalIfErrors() {
        const saleFormErrors = document.querySelector('#saleModalForm .invalid-feedback, #saleModalForm .alert-danger');
        const addSaleModalElement = document.getElementById('addSaleModal');

        if (saleFormErrors && addSaleModalElement) {
            const addSaleModalInstance = new bootstrap.Modal(addSaleModalElement);
            addSaleModalInstance.show();
        }
    }

    // Event listeners
    if (agentSelectModal) {
        agentSelectModal.addEventListener('change', function() {
            toggleClientAgentFields();
            updatePaymentAccountOptions(); // Update accounts based on new selection
        });
        toggleClientAgentFields(); // Set initial state
    }

    if (relatedAcquisitionSelectModal) {
        console.log('Adding event listener to acquisition select');
        relatedAcquisitionSelectModal.addEventListener('change', updatePaymentAccountOptions);
    } else {
        console.log('Acquisition select element not found for event listener');
    }

    const addSaleModalElement = document.getElementById('addSaleModal');
    console.log('Sale modal element found:', !!addSaleModalElement);
    if (addSaleModalElement) {
        console.log('Adding modal event listeners');
        addSaleModalElement.addEventListener('shown.bs.modal', initializeModal);
        
        // Additional modal event handlers for z-index fixes
        addSaleModalElement.addEventListener('show.bs.modal', function() {
            // Ensure modal has proper z-index
            this.style.zIndex = '1055';
        });
        
        addSaleModalElement.addEventListener('hidden.bs.modal', function() {
            // Reset select z-indexes when modal closes
            const selects = this.querySelectorAll('.form-select');
            selects.forEach(select => {
                select.style.zIndex = '';
                select.style.position = '';
            });
        });
    }

    // Show modal if there are form errors (only if sale modal exists)
    if (addSaleModalElement) {
        showModalIfErrors();
    }
    
    // Initialize z-index fixes on page load (only if sale modal exists)
    if (addSaleModalElement) {
        fixSelectDropdownZIndex();
    }
}); 