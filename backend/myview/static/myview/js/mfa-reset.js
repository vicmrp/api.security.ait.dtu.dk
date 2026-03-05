(function () {
    "use strict";

    const STATUS_CLASSES = ["alert-info", "alert-success", "alert-warning", "alert-danger"];

    function toArray(value) {
        return Array.isArray(value) ? value : [];
    }

    function readJson(response) {
        const contentType = response.headers.get("Content-Type") || "";
        if (!contentType.includes("application/json")) {
            throw new Error("Unexpected response from the server.");
        }

        return response.json().then(function (data) {
            if (!response.ok) {
                const message = data && data.message ? data.message : "Bulk reset failed.";
                throw new Error(message);
            }
            return data;
        });
    }

    function buildFailureMessage(failures) {
        return failures
            .map(function (item) {
                if (!item) {
                    return "";
                }
                const label = item.label ? item.label : "Method";
                const error = item.error ? item.error : "Unknown error";
                return label + ": " + error;
            })
            .filter(Boolean)
            .join(" ; ");
    }

    function collectMethodLabels(methods) {
        return methods
            .map(function (method) {
                if (!method) {
                    return "";
                }
                return method.type_label || method.type_key || "Unknown method";
            })
            .filter(Boolean)
            .join(", ");
    }

    function BulkDeleteController(form) {
        this.form = form;
        this.button = document.getElementById("bulk-delete-button");
        this.spinner = document.getElementById("bulk-delete-spinner");
        this.defaultLabel = this.button ? this.button.querySelector("[data-default-label]") : null;
        this.loadingLabel = this.button ? this.button.querySelector("[data-loading-label]") : null;
        this.statusBox = document.getElementById("bulk-delete-status");

        this.defaultConfirmTemplate = "Reset all removable MFA methods for {upn}? This action cannot be undone.";
        this.confirmTemplate = this.button && this.button.dataset.confirmTemplate
            ? this.button.dataset.confirmTemplate
            : this.defaultConfirmTemplate;

        this.bindEvents();
    }

    BulkDeleteController.prototype.bindEvents = function () {
        var self = this;
        this.form.addEventListener("submit", function (event) {
            event.preventDefault();
            self.submit();
        });
    };

    BulkDeleteController.prototype.showStatus = function (kind, message) {
        if (!this.statusBox) {
            return;
        }

        this.statusBox.classList.remove("d-none");
        STATUS_CLASSES.forEach(function (className) {
            this.statusBox.classList.remove(className);
        }, this);
        this.statusBox.classList.add("alert-" + kind);
        this.statusBox.textContent = message;
    };

    BulkDeleteController.prototype.resetStatus = function () {
        if (!this.statusBox) {
            return;
        }
        this.statusBox.classList.add("d-none");
        this.statusBox.textContent = "";
    };

    BulkDeleteController.prototype.setLoading = function (isLoading) {
        if (this.button) {
            this.button.disabled = isLoading;
        }
        if (this.spinner) {
            this.spinner.classList.toggle("d-none", !isLoading);
        }
        if (this.defaultLabel) {
            this.defaultLabel.classList.toggle("d-none", isLoading);
        }
        if (this.loadingLabel) {
            this.loadingLabel.classList.toggle("d-none", !isLoading);
        }
    };

    BulkDeleteController.prototype.getSelectedUserPrincipalName = function () {
        const upnField = this.form.querySelector('input[name="user_principal_name"]');
        if (upnField && upnField.value) {
            return upnField.value;
        }
        return this.form.dataset.selectedUpn || "";
    };

    BulkDeleteController.prototype.confirmSubmission = function (userPrincipalName) {
        const message = this.confirmTemplate.replace("{upn}", userPrincipalName || "the selected user");
        return window.confirm(message);
    };

    BulkDeleteController.prototype.submit = function () {
        var self = this;
        var userPrincipalName = this.getSelectedUserPrincipalName();

        if (!this.confirmSubmission(userPrincipalName)) {
            return;
        }

        this.resetStatus();
        this.setLoading(true);

        const loadingMessage = userPrincipalName
            ? "Resetting MFA methods for " + userPrincipalName + ". This may take a moment..."
            : "Resetting MFA methods. This may take a moment...";
        this.showStatus("info", loadingMessage);

        const formData = new FormData(this.form);

        fetch(this.form.getAttribute("action") || window.location.href, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            },
            credentials: "same-origin"
        })
            .then(readJson)
            .then(function (data) {
                self.handleResponse(data);
            })
            .catch(function (error) {
                self.showStatus("danger", error && error.message ? error.message : "Unable to reset MFA methods.");
                self.setLoading(false);
            });
    };

    BulkDeleteController.prototype.handleResponse = function (data) {
        if (!data) {
            throw new Error("Received empty response from the server.");
        }

        const failures = toArray(data.failures);
        if (failures.length > 0) {
            throw new Error(buildFailureMessage(failures) || "Some authentication methods could not be removed.");
        }

        const remainingDeletable = toArray(data.remaining_deletable_methods);
        if (remainingDeletable.length > 0) {
            const labels = collectMethodLabels(remainingDeletable);
            const pendingMessage = data.message
                ? data.message
                : "Delete requests were accepted, but Microsoft Graph still reports methods: "
                    + (labels || "unknown entries")
                    + ". Refreshing...";
            this.showStatus("warning", pendingMessage);
            window.setTimeout(function () {
                window.location.reload();
            }, 2000);
            return;
        }

        if (data.remaining_error) {
            this.showStatus(
                "warning",
                "Unable to immediately verify remaining methods ("
                    + data.remaining_error
                    + "). Refreshing..."
            );
            window.setTimeout(function () {
                window.location.reload();
            }, 2000);
            return;
        }

        const successMessage = data.message
            ? data.message
            : "All removable authentication methods were deleted. Refreshing...";
        this.showStatus("success", successMessage);
        window.setTimeout(function () {
            window.location.reload();
        }, 1200);
    };

    document.addEventListener("DOMContentLoaded", function () {
        const form = document.getElementById("bulk-delete-form");
        if (!form) {
            return;
        }
        new BulkDeleteController(form);
    });
})();
