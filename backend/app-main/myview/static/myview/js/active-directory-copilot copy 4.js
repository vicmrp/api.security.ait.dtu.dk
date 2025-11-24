console.log('Active Directory Copilot JS loaded');

class App {
    constructor(uiBinder = UIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance(), baseUIBinder = BaseUIBinder.getInstance()) {
        if (!App.instance) {
            this.uiBinder = uiBinder;
            this.baseAppUtils = baseAppUtils;
            this.baseUIBinder = baseUIBinder;
            this._setBindings();
            App.instance = this;
        }
        return App.instance;
    }

    _setBindings() {
        // Send button click
        this.uiBinder.sendBtn.addEventListener('click', (event) => {
            event.preventDefault();
            this.handleUserInput();
        });

        // Enter key in textarea
        this.uiBinder.userInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                this.handleUserInput();
            }
        });
    }

    async handleUserInput() {
        const userInput = this.uiBinder.userInput.value.trim();
        if (userInput === '') {
            return;
        }

        // Append user's message to chat
        this.uiBinder.appendUserMessage(userInput);

        // Clear input
        this.uiBinder.userInput.value = '';

        // Show loading indicator
        this.uiBinder.showLoading();

        // Prepare data to send to server
        let data = {
            'action': 'copilot-active-directory-query',
            'content': JSON.stringify({ 'user': userInput })
        };

        let response;
        let errorOccurred = false;
        try {
            response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', data);
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

    static getInstance(uiBinder = UIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance(), baseUIBinder = BaseUIBinder.getInstance()) {
        if (!App.instance) {
            App.instance = new App(uiBinder, baseAppUtils, baseUIBinder);
        }
        return App.instance;
    }
}

class UIBinder {
    constructor() {
        if (!UIBinder.instance) {
            this.sendBtn = document.getElementById('send-btn');
            this.userInput = document.getElementById('user-input');
            this.chatMessages = document.getElementById('chat-messages');
            this.loadingIndicator = this.createLoadingIndicator();
            UIBinder.instance = this;
        }
        return UIBinder.instance;
    }

    createLoadingIndicator() {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading-indicator';
        loadingDiv.textContent = 'Assistant is typing...';
        return loadingDiv;
    }

    appendUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'user-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.innerHTML = this.escapeHtml(message);

        messageElement.appendChild(messageContent);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    appendAssistantMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'assistant-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.innerHTML = message; // Ensure server sanitizes HTML to prevent XSS

        messageElement.appendChild(messageContent);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    showLoading() {
        this.chatMessages.appendChild(this.loadingIndicator);
        this.scrollToBottom();
    }

    hideLoading() {
        if (this.chatMessages.contains(this.loadingIndicator)) {
            this.chatMessages.removeChild(this.loadingIndicator);
        }
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
