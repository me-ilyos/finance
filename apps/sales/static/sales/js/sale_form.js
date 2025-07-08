/**
 * Sale Form JavaScript
 * Handles modal form interactions, field dependencies, and AJAX calls
 */

document.addEventListener('DOMContentLoaded', function () {
    // Form elements
    const agentSelectModal = document.getElementById('id_agent');
    const clientFullNameModal = document.getElementById('id_client_full_name');
    const clientIDNumberModal = document.getElementById('id_client_id_number');
    const relatedAcquisitionSelectModal = document.getElementById('id_related_acquisition');
    const paidToAccountSelectModal = document.getElementById('id_paid_to_account');
    const paidToAccountWrapper = document.getElementById('wrapper_id_paid_to_account');
    const paidToAccountLabelModal = document.querySelector("label[for='id_paid_to_account']");

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
            paidToAccountWrapper.style.display = 'none';
        } else {
            // No agent - enable client fields, require payment account
            clientFullNameModal.disabled = false;
            clientIDNumberModal.disabled = false;
            
            // Customer sales require immediate payment
            paidToAccountSelectModal.disabled = false;
            paidToAccountWrapper.style.display = 'block';
        }
    }

    /**
     * Update payment account options based on acquisition currency
     */
    async function updatePaymentAccountOptions() {
        if (!relatedAcquisitionSelectModal || !paidToAccountSelectModal) {
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
            const url = `/sales/ajax/get-accounts-for-acquisition/${acquisitionId}/`;
            const response = await fetch(url);
            
            if (!response.ok) {
                paidToAccountSelectModal.innerHTML = '<option value="">Hisoblar yuklanmadi</option>';
                return;
            }
            
            const accounts = await response.json();
            
            if (accounts.error) {
                paidToAccountSelectModal.innerHTML = '<option value="">Xatolik: ' + accounts.error + '</option>';
                return;
            }

            if (accounts.length === 0) {
                paidToAccountSelectModal.innerHTML = '<option value="">Mos hisob topilmadi</option>';
            } else {
                accounts.forEach(account => {
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
        if (agentSelectModal) toggleClientAgentFields();
        if (relatedAcquisitionSelectModal.value) updatePaymentAccountOptions();
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
        relatedAcquisitionSelectModal.addEventListener('change', updatePaymentAccountOptions);
    }

    const addSaleModalElement = document.getElementById('addSaleModal');
    if (addSaleModalElement) {
        addSaleModalElement.addEventListener('shown.bs.modal', initializeModal);
    }

    // Show modal if there are form errors
    showModalIfErrors();
}); 