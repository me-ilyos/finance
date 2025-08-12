/**
 * Dashboard JavaScript
 * Handles account navigation, time updates, and keyboard interactions
 */

// Dashboard.js - Enhanced with transfer functionality

document.addEventListener('DOMContentLoaded', function() {
    const transferModal = document.getElementById('transferModal');
    const depositModal = document.getElementById('depositModal');
    
    initializeAccountSelection();
    initializeTransferModal();
    initializeDepositModal();
    
    // Real-time clock update
    function updateTime() {
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            timeElement.textContent = timeString;
        }
    }
    
    // Update time every second
    setInterval(updateTime, 1000);
    
    // Keyboard navigation for accounts
    document.addEventListener('keydown', function(e) {
        const items = Array.from(document.querySelectorAll('.account-item'));
        const activeItem = document.querySelector('.account-item.active');
        
        if (items.length > 0 && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            e.preventDefault();
            
            let currentIndex = items.indexOf(activeItem);
            let targetIndex;
            
            if (e.key === 'ArrowDown') {
                targetIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % items.length;
            } else {
                targetIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
            }
            
            const targetItem = items[targetIndex];
            const url = targetItem.getAttribute('data-account-url');
            
            if (url) {
                window.location.href = url;
            }
        }
    });
    
    // Initialize tooltips if needed
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (window.bootstrap && tooltipTriggerList.length > 0) {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});

function initializeAccountSelection() {
    const accountItems = document.querySelectorAll('.account-item');
    
    accountItems.forEach(item => {
        item.addEventListener('click', function() {
            const url = this.dataset.accountUrl;
            if (url) {
                window.location.href = url;
            }
        });
        
        item.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const url = this.dataset.accountUrl;
                if (url) {
                    window.location.href = url;
                }
            }
        });
    });
}

function initializeTransferModal() {
    const transferModal = document.getElementById('transferModal');
    const transferForm = document.getElementById('transferForm');
    const fromAccountSelect = document.getElementById('from_account');
    const toAccountSelect = document.getElementById('to_account');
    const amountInput = document.getElementById('amount');
    const conversionRateInput = document.getElementById('conversion_rate');
    const conversionRateGroup = document.getElementById('conversion-rate-group');
    const currencyDisplay = document.getElementById('currency-display');
    const transferPreview = document.getElementById('transfer-preview');
    const previewContent = document.getElementById('preview-content');
    const transferBtnText = document.getElementById('transfer-btn-text');
    const transferDateInput = document.getElementById('transfer_date');
    
    if (!transferModal) {
        return;
    }
    
    // Initialize when modal opens
    transferModal.addEventListener('show.bs.modal', function() {
        const now = new Date();
        transferDateInput.value = now.toISOString();
        resetTransferForm();
    });
    
    // Handle form submission
    transferForm.addEventListener('submit', function(e) {
        e.preventDefault();
        handleTransferSubmit(e);
    });
    
    // Handle account selection changes
    if (fromAccountSelect) {
        fromAccountSelect.addEventListener('change', function() {
            handleAccountSelectionChange.call(this);
        });
    }
    
    if (toAccountSelect) {
        toAccountSelect.addEventListener('change', function() {
            handleAccountSelectionChange.call(this);
        });
    }
    
    if (amountInput) {
        amountInput.addEventListener('input', function() {
            updateTransferPreview();
        });
    }
    
    if (conversionRateInput) {
        conversionRateInput.addEventListener('input', function() {
            updateTransferPreview();
        });
    }
    
    // Reset form when modal is closed
    transferModal.addEventListener('hidden.bs.modal', function() {
        transferForm.reset();
        resetTransferForm();
    });
    
    function handleAccountSelectionChange() {
        const fromAccount = fromAccountSelect.value;
        const toAccount = toAccountSelect.value;
        
        if (fromAccount && toAccount) {
            if (fromAccount === toAccount) {
                showAlert('Bir xil hisobga transfer qilish mumkin emas!', 'warning');
                if (this === toAccountSelect) {
                    toAccountSelect.value = '';
                } else {
                    fromAccountSelect.value = '';
                }
                return;
            }
            
            updateAccountOptions();
        }
        
        updateCurrencyDisplay();
        updateConversionRateVisibility();
        updateTransferPreview();
    }
    
    function updateAccountOptions() {
        const fromAccountValue = fromAccountSelect.value;
        const toAccountValue = toAccountSelect.value;
        
        Array.from(toAccountSelect.options).forEach(option => {
            if (option.value === fromAccountValue) {
                option.disabled = true;
                option.style.display = 'none';
            } else {
                option.disabled = false;
                option.style.display = 'block';
            }
        });
        
        Array.from(fromAccountSelect.options).forEach(option => {
            if (option.value === toAccountValue) {
                option.disabled = true;
                option.style.display = 'none';
            } else {
                option.disabled = false;
                option.style.display = 'block';
            }
        });
    }
    
    function updateCurrencyDisplay() {
        const fromAccount = fromAccountSelect.selectedOptions[0];
        if (fromAccount && fromAccount.dataset.currency) {
            currencyDisplay.textContent = `Valyuta: ${fromAccount.dataset.currency}`;
        } else {
            currencyDisplay.textContent = 'Valyuta: -';
        }
    }
    
    function updateConversionRateVisibility() {
        const fromAccount = fromAccountSelect.selectedOptions[0];
        const toAccount = toAccountSelect.selectedOptions[0];
        
        if (fromAccount && toAccount) {
            const fromCurrency = fromAccount.dataset.currency;
            const toCurrency = toAccount.dataset.currency;
            
            if (fromCurrency !== toCurrency) {
                conversionRateGroup.style.display = 'block';
                conversionRateInput.required = true;
            } else {
                conversionRateGroup.style.display = 'none';
                conversionRateInput.required = false;
                conversionRateInput.value = '';
            }
        } else {
            conversionRateGroup.style.display = 'none';
            conversionRateInput.required = false;
        }
    }
    
    function updateTransferPreview() {
        const fromAccount = fromAccountSelect.selectedOptions[0];
        const toAccount = toAccountSelect.selectedOptions[0];
        const amount = parseFloat(amountInput.value);
        const conversionRate = parseFloat(conversionRateInput.value);
        
        if (!fromAccount || !toAccount || !amount || amount <= 0) {
            if (transferPreview) {
                transferPreview.style.display = 'none';
            }
            return;
        }
        
        const fromCurrency = fromAccount.dataset.currency;
        const toCurrency = toAccount.dataset.currency;
        const fromBalance = parseFloat(fromAccount.dataset.balance);
        
        let previewHTML = `
            <div class="row">
                <div class="col-md-6">
                    <strong>Qaysi hisobdan:</strong><br>
                    ${fromAccount.textContent.trim()}<br>
                    <small class="text-muted">Joriy balans: ${fromBalance.toLocaleString()} ${fromCurrency}</small>
                </div>
                <div class="col-md-6">
                    <strong>Qaysi hisobga:</strong><br>
                    ${toAccount.textContent.trim()}
                </div>
            </div>
            <hr>
        `;
        
        if (fromCurrency !== toCurrency) {
            if (conversionRate && conversionRate > 0) {
                let convertedAmount;
                if (fromCurrency === 'USD' && toCurrency === 'UZS') {
                    convertedAmount = amount * conversionRate;
                } else if (fromCurrency === 'UZS' && toCurrency === 'USD') {
                    convertedAmount = amount / conversionRate;
                } else {
                    if (transferPreview) {
                        transferPreview.style.display = 'none';
                    }
                    return;
                }
                
                previewHTML += `
                    <div class="row">
                        <div class="col-md-6">
                            <strong>Chiqim:</strong><br>
                            ${amount.toLocaleString()} ${fromCurrency}
                        </div>
                        <div class="col-md-6">
                            <strong>Kirim:</strong><br>
                            ${convertedAmount.toLocaleString()} ${toCurrency}
                        </div>
                    </div>
                    <div class="mt-2">
                        <strong>Konversiya kursi:</strong> 1 USD = ${conversionRate.toLocaleString()} UZS
                    </div>
                `;
            } else {
                if (transferPreview) {
                    transferPreview.style.display = 'none';
                }
                return;
            }
        } else {
            previewHTML += `
                <div class="text-center">
                    <strong>Transfer summasi:</strong> ${amount.toLocaleString()} ${fromCurrency}
                </div>
            `;
        }
        
        if (fromBalance < amount) {
            previewHTML += `
                <div class="alert alert-danger mt-3 mb-0">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Hisobda yetarli mablag' yo'q!
                </div>
            `;
        }
        
        if (previewContent) {
            previewContent.innerHTML = previewHTML;
        }
        if (transferPreview) {
            transferPreview.style.display = 'block';
        }
    }
    
    function handleTransferSubmit(e) {
        e.preventDefault();
        
        const fromAccount = fromAccountSelect.selectedOptions[0];
        const toAccount = toAccountSelect.selectedOptions[0];
        const amount = parseFloat(amountInput.value);
        
        if (!fromAccount) {
            showAlert('Iltimos, hisobni tanlang!', 'danger');
            return;
        }
        
        if (!toAccount) {
            showAlert('Qabul qiluvchi hisobni tanlang!', 'danger');
            return;
        }
        
        const fromBalance = parseFloat(fromAccount.dataset.balance);
        
        if (fromBalance < amount) {
            showAlert('Hisobda yetarli mablag\' yo\'q!', 'danger');
            return;
        }
        
        // Check if cross-currency and conversion rate is required
        const fromCurrency = fromAccount.dataset.currency;
        const toCurrency = toAccount.dataset.currency;
        
        if (fromCurrency !== toCurrency && !conversionRateInput.value) {
            showAlert('Turli valyutalar uchun konversiya kursi talab qilinadi!', 'danger');
            return;
        }
        
        const submitButton = transferForm.querySelector('button[type="submit"]');
        const originalText = transferBtnText ? transferBtnText.textContent : 'Transfer qilish';
        
        if (submitButton) {
            submitButton.disabled = true;
        }
        if (transferBtnText) {
            transferBtnText.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Jarayon...';
        }
        
        const formData = new FormData(transferForm);
        
        fetch('/core/transfer/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showAlert('Transfer muvaffaqiyatli amalga oshirildi!', 'success');
                
                const modal = bootstrap.Modal.getInstance(transferModal);
                if (modal) {
                    modal.hide();
                }
                
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                let errorMessage = 'Transfer amalga oshirilmadi.';
                if (data.errors && data.errors.length > 0) {
                    errorMessage = data.errors.join('<br>');
                } else if (data.error) {
                    errorMessage = data.error;
                }
                showAlert(errorMessage, 'danger');
            }
        })
        .catch(error => {
            showAlert('Xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.', 'danger');
        })
        .finally(() => {
            if (submitButton) {
                submitButton.disabled = false;
            }
            if (transferBtnText) {
                transferBtnText.textContent = originalText;
            }
        });
    }
    
    function resetTransferForm() {
        if (conversionRateGroup) {
            conversionRateGroup.style.display = 'none';
        }
        if (conversionRateInput) {
            conversionRateInput.required = false;
        }
        if (currencyDisplay) {
            currencyDisplay.textContent = 'Valyuta: -';
        }
        if (transferPreview) {
            transferPreview.style.display = 'none';
        }
        
        if (fromAccountSelect) {
            Array.from(fromAccountSelect.options).forEach(option => {
                option.disabled = false;
                option.style.display = 'block';
            });
        }
        if (toAccountSelect) {
            Array.from(toAccountSelect.options).forEach(option => {
                option.disabled = false;
                option.style.display = 'block';
            });
        }
    }
}

function initializeDepositModal() {
    const depositModal = document.getElementById('depositModal');
    const depositForm = document.getElementById('depositForm');
    const depositAmountInput = document.getElementById('deposit_amount');
    const depositDateInput = document.getElementById('deposit_date');
    const depositBtnText = document.getElementById('deposit-btn-text');

    if (!depositModal || !depositForm) {
        return;
    }

    depositModal.addEventListener('show.bs.modal', function() {
        const now = new Date();
        if (depositDateInput) {
            depositDateInput.value = now.toISOString();
        }
        if (depositAmountInput) {
            depositAmountInput.value = '';
            depositAmountInput.focus();
        }
    });

    depositForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const amount = parseFloat(depositAmountInput.value);
        if (!amount || amount <= 0) {
            showAlert('Iltimos, to\'g\'ri summani kiriting.', 'danger');
            return;
        }

        const submitButton = depositForm.querySelector('button[type="submit"]');
        const originalText = depositBtnText ? depositBtnText.textContent : 'Kiritish';
        if (submitButton) {
            submitButton.disabled = true;
        }
        if (depositBtnText) {
            depositBtnText.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Jarayon...';
        }

        const formData = new FormData(depositForm);

        fetch('/core/deposit/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showAlert('Kirim muvaffaqiyatli qo\'shildi!', 'success');
                const modal = bootstrap.Modal.getInstance(depositModal);
                if (modal) {
                    modal.hide();
                }
                setTimeout(() => {
                    location.reload();
                }, 800);
            } else {
                let errorMessage = 'Kirimni saqlashda xatolik.';
                if (data.errors && data.errors.length > 0) {
                    errorMessage = data.errors.join('<br>');
                } else if (data.error) {
                    errorMessage = data.error;
                }
                showAlert(errorMessage, 'danger');
            }
        })
        .catch(() => {
            showAlert('Xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.', 'danger');
        })
        .finally(() => {
            if (submitButton) {
                submitButton.disabled = false;
            }
            if (depositBtnText) {
                depositBtnText.textContent = originalText;
            }
        });
    });
}

function showAlert(message, type = 'info') {
    const existingAlerts = document.querySelectorAll('.alert.position-fixed');
    existingAlerts.forEach(alert => alert.remove());
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        if (alertDiv && alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
} 