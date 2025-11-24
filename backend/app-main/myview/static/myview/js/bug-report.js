(function () {
  document.addEventListener('DOMContentLoaded', () => {
    const modalElement = document.getElementById('bugReportModal');
    const formElement = document.getElementById('bugReportForm');
    if (!modalElement || !formElement) {
      return;
    }

    const submitButton = document.getElementById('bugReportSubmitButton');
    const errorContainer = document.getElementById('bugReportFormErrors');
    const locationFields = {
      pageUrl: formElement.querySelector('input[name="page_url"]'),
      pagePath: formElement.querySelector('input[name="page_path"]'),
      siteDomain: formElement.querySelector('input[name="site_domain"]'),
    };

    const fillLocationFields = () => {
      if (locationFields.pageUrl) {
        locationFields.pageUrl.value = window.location.href;
      }
      if (locationFields.pagePath) {
        locationFields.pagePath.value = window.location.pathname + window.location.search;
      }
      if (locationFields.siteDomain) {
        locationFields.siteDomain.value = window.location.origin;
      }
    };

    modalElement.addEventListener('show.bs.modal', () => {
      if (errorContainer) {
        errorContainer.classList.add('d-none');
        errorContainer.textContent = '';
      }
      fillLocationFields();
    });

    const utils = BaseAppUtils.getInstance();
    const notifications = BaseUIBinder.getInstance();

    formElement.addEventListener('submit', async (event) => {
      event.preventDefault();
      fillLocationFields();

      if (submitButton) {
        submitButton.disabled = true;
        submitButton.dataset.originalText = submitButton.dataset.originalText || submitButton.textContent;
        submitButton.textContent = submitButton.getAttribute('data-submitting-text') || 'Submitting…';
      }

      if (errorContainer) {
        errorContainer.classList.add('d-none');
        errorContainer.textContent = '';
      }

      try {
        const formData = new FormData(formElement);
        const response = await utils.restAjax('POST', formElement.action, formData);

        if (response && response.ok) {
          formElement.reset();
          const modalInstance = bootstrap.Modal.getInstance(modalElement);
          if (modalInstance) {
            modalInstance.hide();
          }
          notifications.displayNotification(
            response.message || 'Thanks! Your bug report has been submitted to the team.',
            'alert-success',
            6000,
          );
        } else {
          let message = 'We could not send your report. Please try again.';
          if (response && response.errors) {
            const parsedErrors = Object.values(response.errors)
              .flat()
              .join(' ');
            if (parsedErrors) {
              message = parsedErrors;
            }
          }

          if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.classList.remove('d-none');
          } else {
            notifications.displayNotification(message, 'alert-danger');
          }
        }
      } catch (error) {
        console.error('Failed to submit bug report:', error);
        const message = 'Something went wrong while submitting the report.';
        if (errorContainer) {
          errorContainer.textContent = message;
          errorContainer.classList.remove('d-none');
        }
        notifications.displayNotification(message, 'alert-danger');
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = submitButton.dataset.originalText || 'Submit report';
        }
      }
    });
  });
})();
