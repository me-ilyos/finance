// Force cache reset - version 1.1.0
console.log('Purchases.js loaded successfully - v1.1.0');

document.addEventListener('DOMContentLoaded', function() {
    // --- Initialize Components ---
    initializeDateRangePicker();
    initializeFilterForm();
    setupExportExcelButton();

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

    // --- Setup Export Excel Button ---
    function setupExportExcelButton() {
        const exportBtn = document.getElementById('exportExcel');
        if (exportBtn) {
            exportBtn.addEventListener('click', function(e) {
                e.preventDefault();
                alert('Excel eksport qilish hozircha mavjud emas.');
            });
        }
    }
}); 