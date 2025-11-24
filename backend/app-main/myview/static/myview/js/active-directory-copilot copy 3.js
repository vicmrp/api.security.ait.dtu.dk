console.log('Active Directory Copilot JS loaded');

class App {
    constructor(uiBinder = UIBinder.getInstance(), appUtils = AppUtils.getInstance()) {
        if (!App.instance) {
            this.uiBinder = uiBinder;
            this.appUtils = appUtils;
            this._setBindings();
            App.instance = this;
        }
        return App.instance;
    }

    _setBindings() {
        // Send button click
        this.uiBinder.sendBtn.on('click', (event) => {
            event.preventDefault();
            this.handleUserInput();
        });

        // Enter key in textarea
        this.uiBinder.userInput.on('keypress', (event) => {
            if (event.which === 13 && !event.shiftKey) {
                event.preventDefault();
                this.handleUserInput();
            }
        });
    }

    async handleUserInput() {
        const userInput = this.uiBinder.userInput.val().trim();
        if (userInput === '') {
            return;
        }

        // Append user's message to chat
        // this.uiBinder.appendUserMessage(userInput);

        // Clear input
        this.uiBinder.userInput.val('');

        // Show loading indicator
        // this.uiBinder.showLoading();

        // Prepare data to send to server
        let data = {
            'action': 'copilot-active-directory-query',
            'content': JSON.stringify({ 'user': userInput })
        };

        let response;
        let errorOccurred = false;
        try {
            response = await this.appUtils.restAjax('POST', '/myview/ajax/', data);
        } catch (error) {
            console.log('Error:', error);
            this.uiBinder.appendAssistantMessage(`An error occurred: ${error}`);
            errorOccurred = true;
        } finally {
            // Hide loading indicator
            this.uiBinder.hideLoading();
        }

        if (!errorOccurred) {
            // Check if response contains error
            if (response.error) {
                this.uiBinder.appendAssistantMessage(`Error: ${response.error}`);
                return;
            }

            // Extract explanation and other data
            const explanation = response.explanation;
            if (explanation) {
                this.uiBinder.appendAssistantMessage(explanation);
            }

            // Display the number of returned objects
            const numObjects = response.number_of_returned_objects;
            if (numObjects !== undefined) {
                this.uiBinder.appendAssistantMessage(`Number of returned objects: ${numObjects}`);
            }

            // Provide link to download XLSX file
            const xlsxUrl = response.xlsx_file_url;
            if (xlsxUrl) {
                this.uiBinder.appendAssistantMessage(`You can download the results <a href="${xlsxUrl}" target="_blank">here</a>.`);
            }
        }
    }

    static getInstance(uiBinder = UIBinder.getInstance(), appUtils = AppUtils.getInstance()) {
        if (!App.instance) {
            App.instance = new App(uiBinder, appUtils);
        }
        return App.instance;
    }
}

class UIBinder {
    constructor() {
        if (!UIBinder.instance) {
            this.sendBtn = $('#send-btn');
            this.userInput = $('#user-input');
            this.chatMessages = $('#chat-messages');
            this.loadingIndicator = $('<div class="loading-indicator">Assistant is typing...</div>');
            UIBinder.instance = this;
        }
        return UIBinder.instance;
    }

    appendUserMessage(message) {
        const messageElement = `
            <div class="message user-message">
                <div class="message-content">${this.escapeHtml(message)}</div>
            </div>
        `;
        this.chatMessages.append(messageElement);
        this.scrollToBottom();
    }

    appendAssistantMessage(message) {
        const messageElement = `
            <div class="message assistant-message">
                <div class="message-content">${message}</div>
            </div>
        `;
        this.chatMessages.append(messageElement);
        this.scrollToBottom();
    }

    showLoading() {
        this.chatMessages.append(this.loadingIndicator);
        this.scrollToBottom();
    }

    hideLoading() {
        this.loadingIndicator.remove();
    }

    scrollToBottom() {
        this.chatMessages.scrollTop(this.chatMessages[0].scrollHeight);
    }

    escapeHtml(text) {
        return $('<div>').text(text).html();
    }

    static getInstance() {
        if (!UIBinder.instance) {
            UIBinder.instance = new UIBinder();
        }
        return UIBinder.instance;
    }
}

class AppUtils {
    constructor() {
        if (!AppUtils.instance) {
            AppUtils.instance = this;
        }
        return AppUtils.instance;
    }

    restAjax(method, url, data) {
        return new Promise(function (resolve, reject) {
            $.ajax({
                type: method,
                url: url,
                data: data,
                dataType: 'json',
                contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
                success: function (response) {
                    resolve(response);
                },
                error: function (xhr, status, error) {
                    let errorMsg = xhr.responseJSON ? xhr.responseJSON.error : error;
                    reject(errorMsg);
                }
            });
        });
    }

    static getInstance() {
        if (!AppUtils.instance) {
            AppUtils.instance = new AppUtils();
        }
        return AppUtils.instance;
    }
}

$(document).ready(function () {
    const app = App.getInstance();
});
