console.log('Frontpage JS loaded');


class App {
    constructor(uiBinder = UIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), appUtils = AppUtils.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {

        if (!App.instance) {
            this.uiBinder = uiBinder;
            this.baseUIBinder = baseUIBinder;
            this.appUtils = appUtils;
            this.baseAppUtils = baseAppUtils;
            this.selectedLimiterTypes = new Set();
            this._setBindings();
            App.instance = this;
        }

        return App.instance;
    }


    _setBindings() {

        if (this.uiBinder.rotateApiKeyBtn.length) {
            const rotateApiKeyBtn = `#${this.uiBinder.rotateApiKeyBtn[0].id}`;
            const modalId = 'apiKeyRotateModal';
            const modalConfirmBtn = 'modalRotateApiKeyConfirmBtn';
            this.baseAppUtils.setModal(rotateApiKeyBtn, modalId, {
                title: 'Rotate API key',
                body: '<p>Rotating your API key will immediately invalidate your previous key. Are you sure you want to continue?</p>',
                footer: `
                    <button type="button" class="btn btn-danger" id="${modalConfirmBtn}">Rotate API key <span id="loadingSpinnerRotateApiKeyBtn" class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="display: none;"></span></button>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">No, cancel</button>
                `,
                eventListeners: [
                    {
                        selector: `#${modalConfirmBtn}`,
                        event: 'click',
                        handler: (event) => {
                            this.handleRotateApiKey(event, modalId);
                        }
                    }
                ]
            });
        }

        if (this.uiBinder.toggleApiKeyVisibility.length) {
            this.uiBinder.toggleApiKeyVisibility.on('click', (event) => {
                this.handleToggleApiKeyVisibility(event);
            });
        }

        if (this.uiBinder.filterLimiterTypeBtn.length) {
            const filterLimiterBtnSelector = `#${this.uiBinder.filterLimiterTypeBtn[0].id}`;
            const limiterModalId = 'limiterTypeFilterModal';
            const availableLimiterTypes = this.appUtils.getAvailableLimiterTypes();

            const modalBody = this.appUtils.generateLimiterTypeOptionsHtml(availableLimiterTypes);
            const modalFooter = `
                <button type="button" class="btn btn-primary" id="applyLimiterFilterBtn">Apply filter</button>
                <button type="button" class="btn btn-outline-secondary" id="clearLimiterFilterBtn">Clear filter</button>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            `;

            this.baseAppUtils.setModal(filterLimiterBtnSelector, limiterModalId, {
                title: 'Filter endpoints by limiter type',
                body: modalBody,
                footer: modalFooter,
                eventListeners: [
                    {
                        selector: '#applyLimiterFilterBtn',
                        event: 'click',
                        handler: (event) => {
                            this.handleApplyLimiterFilter(event, limiterModalId);
                        }
                    },
                    {
                        selector: '#clearLimiterFilterBtn',
                        event: 'click',
                        handler: (event) => {
                            this.handleClearLimiterFilter(event, limiterModalId);
                        }
                    }
                ]
            });

            const limiterModalElement = document.getElementById(limiterModalId);
            if (limiterModalElement) {
                limiterModalElement.addEventListener('show.bs.modal', () => {
                    this.populateLimiterModalSelections(limiterModalId);
                });
            }
        }

        this.updateLimiterFilterSummary();
        this.filterEndpointTable();
        this.fetchInitialApiKey();
    }




    async handleRotateApiKey(event, modalId) {
        event.preventDefault();
        const button = $(event.currentTarget);
        const spinner = $('#loadingSpinnerRotateApiKeyBtn');
        spinner.show();
        button.prop('disabled', true);

        const formData = new FormData();
        formData.append('action', 'rotate_api_token');

        let response;
        let errorOccurred = false;
        try {
            response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', formData);
        } catch (error) {
            console.log('Error:', error);
            this.baseUIBinder.displayNotification('Failed to rotate API key. Please try again.', 'alert-danger');
            errorOccurred = true;
        } finally {
            if (!errorOccurred) {
                const apiKey = response && response.api_token ? response.api_token : null;
                if (apiKey) {
                    this.updateApiKeyInput(apiKey);
                    this.baseUIBinder.displayNotification('API key rotated successfully!', 'alert-success');
                } else {
                    this.baseUIBinder.displayNotification('No API key was returned. Please try again.', 'alert-danger');
                }

                const modalElement = document.getElementById(modalId);
                if (modalElement) {
                    const modalInstance = bootstrap.Modal.getInstance(modalElement);
                    if (modalInstance) {
                        modalInstance.hide();
                    }
                }
            }

            spinner.hide();
            button.prop('disabled', false);
        }
    }

    handleToggleApiKeyVisibility(event) {
        event.preventDefault();
        if (!this.uiBinder.apiKeyInput.length) {
            return;
        }

        const input = this.uiBinder.apiKeyInput[0];
        const button = $(event.currentTarget);
        const icon = button.find('i');
        const isHidden = input.type === 'password';

        if (isHidden) {
            input.type = 'text';
            button.attr('aria-label', 'Hide API key');
            icon.removeClass('bi-eye-slash').addClass('bi-eye');
        } else {
            input.type = 'password';
            button.attr('aria-label', 'Show API key');
            icon.removeClass('bi-eye').addClass('bi-eye-slash');
        }
    }

    updateApiKeyInput(value) {
        if (!this.uiBinder.apiKeyInput.length) {
            return;
        }

        this.uiBinder.apiKeyInput.val(value);
        this.uiBinder.apiKeyInput.attr('type', 'password');
        this.uiBinder.apiKeyInput.attr('placeholder', '');

        if (this.uiBinder.toggleApiKeyVisibility.length) {
            const toggleButton = this.uiBinder.toggleApiKeyVisibility;
            toggleButton.prop('disabled', false);
            toggleButton.attr('aria-label', 'Show API key');
            const icon = toggleButton.find('i');
            icon.removeClass('bi-eye').addClass('bi-eye-slash');
        }
    }

    async fetchInitialApiKey() {
        if (!this.uiBinder.apiKeyInput.length) {
            return;
        }

        try {
            const response = await this.baseAppUtils.restAjax('GET', '/myview/api/token/');
            const apiKey = response && response.api_token ? response.api_token : null;
            if (apiKey) {
                this.updateApiKeyInput(apiKey);
            } else {
                this.baseUIBinder.displayNotification('No API key is available for your account yet.', 'alert-warning');
            }
        } catch (error) {
            console.error('Failed to fetch API key:', error);
            this.baseUIBinder.displayNotification('Failed to fetch your API key. Please try again.', 'alert-danger');
        }
    }

    handleApplyLimiterFilter(event, modalId) {
        event.preventDefault();
        const selectedCheckboxes = Array.from(document.querySelectorAll(`#${modalId} input[type="checkbox"]:checked`));
        const selectedValues = selectedCheckboxes.map((checkbox) => checkbox.value);

        this.selectedLimiterTypes = new Set(selectedValues);
        this.filterEndpointTable();
        this.updateLimiterFilterSummary();

        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (modalInstance) {
                modalInstance.hide();
            }
        }
    }

    handleClearLimiterFilter(event, modalId) {
        event.preventDefault();
        this.selectedLimiterTypes.clear();
        this.filterEndpointTable();
        this.updateLimiterFilterSummary();
        this.populateLimiterModalSelections(modalId);
    }

    filterEndpointTable() {
        const rows = document.querySelectorAll('[data-endpoint-row]');
        const hasActiveFilters = this.selectedLimiterTypes && this.selectedLimiterTypes.size > 0;

        rows.forEach((row) => {
            const limiterType = (row.getAttribute('data-limiter-type') || 'None').trim() || 'None';
            if (!hasActiveFilters || this.selectedLimiterTypes.has(limiterType)) {
                row.classList.remove('d-none');
            } else {
                row.classList.add('d-none');
            }
        });
    }

    populateLimiterModalSelections(modalId) {
        const modalElement = document.getElementById(modalId);
        if (!modalElement) {
            return;
        }

        const checkboxes = modalElement.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach((checkbox) => {
            if (!this.selectedLimiterTypes || this.selectedLimiterTypes.size === 0) {
                checkbox.checked = false;
            } else {
                checkbox.checked = this.selectedLimiterTypes.has(checkbox.value);
            }
        });
    }

    updateLimiterFilterSummary() {
        if (!this.uiBinder.limiterFilterSummary || this.uiBinder.limiterFilterSummary.length === 0) {
            return;
        }

        if (!this.selectedLimiterTypes || this.selectedLimiterTypes.size === 0) {
            this.uiBinder.limiterFilterSummary.text('');
            this.uiBinder.limiterFilterSummary.addClass('d-none');
            return;
        }

        const summaryText = Array.from(this.selectedLimiterTypes).join(', ');
        this.uiBinder.limiterFilterSummary.text(summaryText);
        this.uiBinder.limiterFilterSummary.removeClass('d-none');
    }
    static getInstance(uiBinder = UIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), appUtils = AppUtils.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!App.instance) {
            App.instance = new App(uiBinder, baseUIBinder, appUtils, baseAppUtils);
        }
        return App.instance;
    }
}


class AppUtils {
    constructor() {
        if (!AppUtils.instance) {
            AppUtils.instance = this;
        }
        return AppUtils.instance;
    }


    printHelloWorld() {
        console.log('Hello World');
        return "Hello World";
    }


    getAvailableLimiterTypes() {
        if (this.availableLimiterTypes) {
            return this.availableLimiterTypes;
        }

        const scriptElement = document.getElementById('available-limiter-types-data');
        if (!scriptElement) {
            this.availableLimiterTypes = [];
            return this.availableLimiterTypes;
        }

        try {
            const parsedData = JSON.parse(scriptElement.textContent);
            this.availableLimiterTypes = Array.isArray(parsedData) ? parsedData : [];
        } catch (error) {
            console.error('Failed to parse available limiter types:', error);
            this.availableLimiterTypes = [];
        }

        return this.availableLimiterTypes;
    }

    escapeHtml(value) {
        if (typeof value !== 'string') {
            return '';
        }

        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    generateLimiterTypeOptionsHtml(limiterTypes = []) {
        if (!Array.isArray(limiterTypes) || limiterTypes.length === 0) {
            return '<p class="mb-0">No limiter types available.</p>';
        }

        const optionsHtml = limiterTypes.map((type, index) => {
            const safeValue = typeof type === 'string' ? type.trim() : '';
            const escapedLabel = this.escapeHtml(safeValue || 'None');
            const checkboxId = `limiterTypeOption-${index}`;
            return `
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${escapedLabel}" id="${checkboxId}">
                    <label class="form-check-label" for="${checkboxId}">${escapedLabel}</label>
                </div>
            `;
        }).join('');

        return `<fieldset><legend class="visually-hidden">Limiter type filters</legend>${optionsHtml}</fieldset>`;
    }


    static getInstance() {
        if (!AppUtils.instance) {
            AppUtils.instance = new AppUtils();
        }
        return AppUtils.instance;
    }
}




class UIBinder {
    constructor() {
        if (!UIBinder.instance) {
            this.apiKeyInput = $('#apiKeyInput');
            this.toggleApiKeyVisibility = $('#toggleApiKeyVisibility');
            this.rotateApiKeyBtn = $('#rotateApiKeyBtn');
            this.filterLimiterTypeBtn = $('#filterLimiterTypeBtn');
            this.limiterFilterSummary = $('#limiterFilterSummary');
            UIBinder.instance = this;
        }
        return UIBinder.instance;
    }




    static getInstance() {
        if (!UIBinder.instance) {
            UIBinder.instance = new UIBinder();
        }
        return UIBinder.instance;
    }
}





document.addEventListener('DOMContentLoaded', function () {
    const app = App.getInstance();
});
