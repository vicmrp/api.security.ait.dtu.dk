

document.addEventListener('DOMContentLoaded', function () {


  BaseAppUtils.initializeTooltips();


});







// base class for all UI managers
class BaseUIBinder {
  constructor() {

    // this simulates a singleton pattern
    if (!BaseUIBinder.instance) {
      this.baseNotificationsContainer = $('#base-notifications-container');
      BaseUIBinder.instance = this;
    }

    return BaseUIBinder.instance;

  }



  displayNotification(message, type, timeout = 0) {
    // types of alerts: alert-primary, alert-secondary, alert-success, alert-danger, alert-warning, alert-info, alert-light, alert-dark

    // clear any existing notifications
    this.baseNotificationsContainer.html('');

    const notificationHtml = `<div class="alert ${type} alert-dismissible fade show" role="alert">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>`;

    this.baseNotificationsContainer.html(notificationHtml); // Set the new notification

    if (timeout > 0) {
      setTimeout(() => {
        this.baseNotificationsContainer.html(''); // Clear the notification after the
      }, timeout);
    }

    return true
  }





  static getInstance() {
    if (!BaseUIBinder.instance) {
      BaseUIBinder.instance = new BaseUIBinder();
    }
    return BaseUIBinder.instance;
  }

  // Add more methods as needed to interact with other containers or elements
}






























class BaseAppUtils {
  constructor() {
    if (!BaseAppUtils.instance) {
      BaseAppUtils.instance = this;
    }
    return BaseAppUtils.instance;
  }

  /**
   * Perform a REST AJAX request.
   * @param {string} method - The HTTP method ('GET', 'POST', 'DELETE', etc.)
   * @param {string} url - The URL endpoint.
   * @param {Object|FormData|string} data - The data to be sent. Pass an object for form data, FormData for multipart form data, or a JSON string for JSON data.
   * @param {Object} headers - Optional. Additional headers to send.
   * @returns {Promise<Object>} The response data or an error object.
   */
  async restAjax(method, url, data = null, headers = {}) {
    // Add CSRF token for Django compatibility
    const csrfToken = this.getCookie('csrftoken');
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    let body = null;

    if (data) {
      if (data instanceof FormData) {
        // If data is FormData, do not set Content-Type header
        body = data;
      } else if (typeof data === 'object') {
        // If data is a plain object, send it as application/x-www-form-urlencoded
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
        body = new URLSearchParams(data).toString();
      } else if (typeof data === 'string') {
        // If data is a string, assume it's JSON
        headers['Content-Type'] = 'application/json';
        body = data;
      } else {
        throw new Error('Invalid data type: data must be an Object, FormData, or JSON string');
      }
    }

    // Perform the request using fetch
    try {
      const response = await fetch(url, {
        method: method,
        headers: headers,
        body: (method !== 'GET' && method !== 'HEAD') ? body : undefined,
        credentials: 'include' // Ensure credentials are sent with requests (e.g., cookies)
      });

      const contentType = response.headers.get('Content-Type') || '';
      let parsedData = null;

      if (response.status !== 204) {
        try {
          if (contentType.includes('application/json')) {
            parsedData = await response.json();
          } else {
            parsedData = await response.text();
          }
        } catch (parseError) {
          console.error('Failed to parse response body:', parseError);
        }
      }

      const metadata = {
        status: response.status,
        ok: response.ok,
      };

      let normalizedResponse;

      if (parsedData === null || typeof parsedData === 'undefined') {
        normalizedResponse = { ...metadata, data: null };
      } else if (Array.isArray(parsedData)) {
        normalizedResponse = [...parsedData];
        normalizedResponse.data = parsedData;
        Object.assign(normalizedResponse, metadata);
      } else if (typeof parsedData === 'object') {
        normalizedResponse = { ...parsedData, ...metadata, data: parsedData };
      } else {
        normalizedResponse = { ...metadata, data: parsedData };
      }

      return normalizedResponse;

    } catch (error) {
      console.error('Request failed:', error);
      throw error; // Re-throw the error for further handling if needed
    }
  }

  getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  printCurlCommand(url, csrfToken, formData) {
    let dataString = new URLSearchParams(formData).toString();
    let command = `curl -X POST '${url}' -H 'Content-Type: application/x-www-form-urlencoded' -H 'X-CSRFToken: ${csrfToken}' -d '${dataString}' -b cookies.txt`;
    console.log(command);
  }

  updateSessionStorage(data, prefix) {
    // example updateSessionStorage({userPrincipalObj: data}, 'myApp');

    // Iterate over each key-value pair in the data object
    for (let key in data) {
      if (data.hasOwnProperty(key)) {
        // Convert the data to a JSON string
        let jsonData = JSON.stringify(data[key]);

        // Save the data to session storage with a unique key
        sessionStorage.setItem(`${prefix}-${key}`, jsonData);
      }
    }
  }

  static initializeTooltips() {
    try {
      // Initialize tooltips with HTML content
      const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"][data-bs-html="true"]'));
      tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl, {
          html: true  // Enables HTML content inside tooltips
        });
      });
    } catch (error) {
      console.error('Failed to load tooltips styling:', error);
      throw new Error('Failed to load tooltips styling');
    }
  }

  /**
   * Dynamically creates and attaches a modal to a trigger element.
   * 
   * @param {string} triggerSelector - Selector for the element that triggers the modal.
   * @param {string} modalId - Unique ID for the modal.
   * @param {Object} options - Optional settings for modal customization.
   * 
   * example usage:
   * setModal('#myButton', 'myModal', {
   *   title: 'My Modal Title',
   *   body: '<p>This is the modal body</p>',
   *   footer: '<button type="button" class="btn btn-primary" data-bs-dismiss="modal">Close</button>',
   *   eventListeners: [
   *   {
   *     selector: '.save-btn',
   *     event: 'click',
   *     handler: function() {
   *       alert('Save button clicked');
   *     }
   *   }
   *   ]
   *   });
   *
   * note that you dont need to set an event listener, you can do that after the modal is created
   * 
   * @returns {Object} - The modal instance.
   * 
   */
  setModal(triggerSelector, modalId, options = {}) {
    // this function assumes that each modal is unique to a trigger

    // Check if an element with the ID stored in modalId exists in the document
    if ($('#' + modalId).length) {
      // If the element exists, remove it from the document
      $('#' + modalId).remove();
    }

    // If options are provided, use them to update the modal
    const modalType = options.modalType || 'modal-dialog';
    const modalContent = options.modalContent || 'modal-content';
    const modalTitle = options.title || 'Default Modal Title';
    const modalBody = options.body || 'Default Modal Body';
    const modalFooter = options.footer || `<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>`;
    const eventListeners = options.eventListeners || []; // This will be an array of event listener descriptions

    // Create the modal HTML with the provided content and a unique ID
    const modalHtml = `
      <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
          <div class="${modalType}">
              <div class="${modalContent}">
                  <div class="modal-header">
                      <h5 class="modal-title" id="${modalId}Label">${modalTitle}</h5>
                      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                  </div>
                  <div class="modal-body">
                      ${modalBody}
                  </div>
                  <div class="modal-footer">
                      ${modalFooter}
                  </div>
              </div>
          </div>
      </div>
    `;

    // Append the modal to the body
    $('body').append(modalHtml);
    const modalInstance = new bootstrap.Modal(document.getElementById(modalId), { keyboard: false });

    // Attach event listeners specified in options
    eventListeners.forEach(({ selector, event, handler }) => {
      // Remove existing event listeners to prevent multiple bindings
      $(document).off(event, `#${modalId} ${selector}`).on(event, `#${modalId} ${selector}`, handler);
    });

    // Detach existing click events to prevent multiple bindings
    $(triggerSelector).off('click').on('click', function () {
      modalInstance.show();
    });

    return modalInstance;
  }

  updateModalContent(modalID, content = { modalTitle: '', modalBody: '', modalFooter: '', eventListeners: [] }) {
    // Get the modal
    const modal = $('#' + modalID);

    // Update the modal title if provided
    if (content.modalTitle) {
      modal.find('.modal-title').text(content.modalTitle);
    }

    // Update the modal body if provided
    if (content.modalBody) {
      modal.find('.modal-body').html(content.modalBody);
    }

    // Update the modal footer if provided
    if (content.modalFooter) {
      modal.find('.modal-footer').html(content.modalFooter);
    }

    // Attach event listeners specified in options
    const eventListeners = content.eventListeners || [];
    eventListeners.forEach(({ selector, event, handler }) => {
      // Remove existing event listeners to prevent multiple bindings
      $(document).off(event, `#${modalID} ${selector}`).on(event, `#${modalID} ${selector}`, handler);
    });
  }

  static getInstance() {
    if (!BaseAppUtils.instance) {
      BaseAppUtils.instance = new BaseAppUtils();
    }
    return BaseAppUtils.instance;
  }
}






