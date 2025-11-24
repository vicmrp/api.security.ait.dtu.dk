class CopilotApp {
    constructor(uiBinder = CopilotUIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), appUtils = CopilotAppUtils.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!CopilotApp.instance) {
            this.uiBinder = uiBinder;
            this.baseUIBinder = baseUIBinder;
            this.appUtils = appUtils;
            this.baseAppUtils = baseAppUtils;
            this._setBindings();
            CopilotApp.instance = this;
        }

        return CopilotApp.instance;
    }

    _setBindings() {
        this.uiBinder.copilotSubmitBtn.on('click', this.handleCopilotRequest.bind(this));
        this.uiBinder.canonicalNameSwitch.on('change', this.toggleCanonicalNameNotation.bind(this));

        this.uiBinder.copilotTextareaField.on('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                this.handleCopilotRequest(event);
            }
        });

        this.uiBinder.downloadJsonBtn.on('click', this.appUtils.downloadJsonFile.bind(this.appUtils));
    }

    toggleCanonicalNameNotation() {
        const baseDnField = this.uiBinder.baseDnField;
        const isCanonical = this.uiBinder.canonicalNameSwitch.is(':checked');

        let value = baseDnField.val();
        if (isCanonical) {
            // Convert Base DN to Canonical Name Notation
            const canonicalName = this.appUtils.convertToCanonicalName(value);
            baseDnField.val(canonicalName);
        } else {
            // Convert Canonical Name Notation to Base DN
            const baseDn = this.appUtils.convertToBaseDn(value);
            baseDnField.val(baseDn);
        }
    }

    async handleCopilotRequest(event) {
        event.preventDefault();
        console.log("Handling copilot request");

        let formData = new FormData();
        formData.append('action', 'copilot-active-directory-query');
        formData.append('content', JSON.stringify({ user: this.uiBinder.copilotTextareaField.val() }));

        this.uiBinder.loadingSpinnerCopilot.show();
        this.uiBinder.copilotSubmitBtn.prop('disabled', true);

        let response;

        try {
            response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', formData);

            if (response.active_directory_query_result) {
                this.uiBinder.copilotResultContainer.show();
                this.uiBinder.copilotResult.text(JSON.stringify(response, null, 2));

                // Update the number of returned objects
                const numberOfReturnedObjects = response.active_directory_query_result.length;
                this.uiBinder.returnedObjectsCount.text(numberOfReturnedObjects);

                // Populate the Excel table
                this.populateExcelTable(response.active_directory_query_result);

                // Store the result for download
                this.appUtils.queryResult = response;

                if (response.xlsx_file_url) {
                    this.uiBinder.downloadXlsxBtn.attr('href', response.xlsx_file_url);
                    this.uiBinder.downloadXlsxBtn.attr('download', response.xlsx_file_name);
                    this.uiBinder.downloadXlsxBtn.show();
                } else {
                    this.uiBinder.downloadXlsxBtn.hide();
                }

            } else if (response.error) {
                this.baseUIBinder.displayNotification(response.error, 'alert-warning');
            } else {
                this.baseUIBinder.displayNotification('An unknown error occurred.', 'alert-warning');
            }
        } catch (error) {
            console.log('Error:', error);
            this.baseUIBinder.displayNotification('An error occurred while processing your request.', 'alert-danger');
        } finally {
            this.uiBinder.loadingSpinnerCopilot.hide();
            this.uiBinder.copilotSubmitBtn.prop('disabled', false);
        }
    }

    static getInstance(uiBinder = CopilotUIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), appUtils = CopilotAppUtils.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!CopilotApp.instance) {
            CopilotApp.instance = new CopilotApp(uiBinder, baseUIBinder, appUtils, baseAppUtils);
        }
        return CopilotApp.instance;
    }
}

class CopilotAppUtils {
    constructor() {
        if (!CopilotAppUtils.instance) {
            this.queryResult = null; // Store the result for downloading
            CopilotAppUtils.instance = this;
        }
        return CopilotAppUtils.instance;
    }

    downloadJsonFile() {
        if (this.queryResult) {
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(this.queryResult, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", "active_directory_query_result.json");
            document.body.appendChild(downloadAnchorNode); // Required for Firefox
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        }
    }

    // Utility function to convert Base DN to Canonical Name Notation
    convertToCanonicalName(baseDn) {
        return baseDn
            .replace(/DC=/g, '')
            .replace(/OU=/g, '')
            .replace(/,/g, '/');
    }

    // Utility function to convert Canonical Name Notation to Base DN
    convertToBaseDn(canonicalName) {
        const parts = canonicalName.split('/');
        let baseDn = [];
        for (let i = parts.length - 1; i >= 0; i--) {
            baseDn.push(i === 0 ? `OU=${parts[i]}` : `DC=${parts[i]}`);
        }
        return baseDn.join(',');
    }

    static getInstance() {
        if (!CopilotAppUtils.instance) {
            CopilotAppUtils.instance = new CopilotAppUtils();
        }
        return CopilotAppUtils.instance;
    }
}

class CopilotUIBinder {
    constructor() {
        if (!CopilotUIBinder.instance) {
            this.copilotForm = $('#copilot-form');
            this.downloadXlsxBtn = $('#download-xlsx-btn');
            this.copilotSubmitBtn = $('#copilot-submit-btn');
            this.copilotTextareaField = $('#copilot-submit-textarea-field');
            this.toggleViewBtn = $('#toggle-view');
            this.jsonView = $('#json-view');
            this.excelView = $('#excel-view');
            this.excelTable = $('#excel-table');
            this.returnedObjectsCount = $('#returned_objects_count');
            this.loadingSpinnerCopilot = $('#loadingSpinnerCopilot');
            this.copilotResultContainer = $('#copilot-result-container');
            this.copilotResult = $('#copilot-result');
            this.downloadJsonBtn = $('#download-json-btn');
            this.baseDnField = $('#base_dn');
            this.canonicalNameSwitch = $('#canonical_name_switch');
            CopilotUIBinder.instance = this;
        }

        return CopilotUIBinder.instance;
    }

    static getInstance() {
        if (!CopilotUIBinder.instance) {
            CopilotUIBinder.instance = new CopilotUIBinder();
        }
        return CopilotUIBinder.instance;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const app = CopilotApp.getInstance();
});
