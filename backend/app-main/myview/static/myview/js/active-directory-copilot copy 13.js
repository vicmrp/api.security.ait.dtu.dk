console.log('Active Directory Copilot JS loaded');

class App {
    constructor(uiBinder = UIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!App.instance) {
            this.uiBinder = uiBinder;
            this.baseAppUtils = baseAppUtils;
            this.currentThreadId = null;
            this._setBindings();
            this.loadChatThreads();
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

        // New Chat button
        this.uiBinder.newChatBtn.addEventListener('click', (event) => {
            event.preventDefault();
            this.createNewChat();
        });

        // Chat thread click
        this.uiBinder.chatList.addEventListener('click', (event) => {
            const threadItem = event.target.closest('.chat-thread-item');
            if (threadItem && !event.target.classList.contains('delete-chat-btn')) {
                const threadId = threadItem.dataset.threadId;
                this.loadChatMessages(threadId);
            }

            // Delete chat thread
            const deleteBtn = event.target.closest('.delete-chat-btn');
            if (deleteBtn) {
                const threadId = deleteBtn.dataset.threadId;
                const threadTitle = deleteBtn.parentElement.querySelector('.thread-title').textContent;
                this.confirmDeleteChatThread(threadId, threadTitle);
            }
        });
    }

    async createNewChat() {
        try {
            const response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', {
                'action': 'create_chat_thread'
            });
            this.currentThreadId = response.thread_id;
            this.uiBinder.clearChatMessages();
            this.loadChatThreads();
        } catch (error) {
            console.error('Error creating new chat:', error);
        }
    }

    async loadChatThreads() {
        try {
            const response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', {
                'action': 'get_chat_threads'
            });
            this.uiBinder.populateChatThreads(response.threads);
            if (response.threads.length > 0 && !this.currentThreadId) {
                this.loadChatMessages(response.threads[0].id);
            }
        } catch (error) {
            console.error('Error loading chat threads:', error);
        }
    }

    async loadChatMessages(threadId) {
        this.currentThreadId = threadId;
        try {
            const response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', {
                'action': 'get_chat_messages',
                'thread_id': threadId
            });
            this.uiBinder.clearChatMessages();
            response.messages.forEach(message => {
                if (message.role === 'user') {
                    this.uiBinder.appendUserMessage(message.content, message.timestamp);
                } else if (message.role === 'assistant') {
                    this.uiBinder.appendAssistantMessage(JSON.parse(message.content), message.timestamp);
                }
            });
        } catch (error) {
            console.error('Error loading chat messages:', error);
        }
    }

    async handleUserInput() {
        const userInput = this.uiBinder.userInput.value.trim();
        if (userInput === '') {
            return;
        }

        if (!this.currentThreadId) {
            await this.createNewChat();
        }

        // Append user's message to chat
        this.uiBinder.appendUserMessage(userInput);

        // Clear input
        this.uiBinder.userInput.value = '';

        // Show loading indicator
        this.uiBinder.showLoading();

        try {
            const response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', {
                'action': 'send_message',
                'thread_id': this.currentThreadId,
                'message': userInput
            });

            // Hide loading indicator
            this.uiBinder.hideLoading();

            // Display assistant's response
            const assistantResponse = response.assistant_response;
            const assistantMessageElement = this.uiBinder.appendAssistantMessage(assistantResponse);

            // Reload chat threads to update titles
            this.loadChatThreads();

            // Check if auto-run is enabled
            if (this.uiBinder.autoRunToggle.checked) {
                // Simulate clicking the "Run Query" button
                const runQueryBtn = assistantMessageElement.querySelector('.run-query-btn');
                if (runQueryBtn) {
                    runQueryBtn.click();
                }
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.uiBinder.hideLoading();
            this.uiBinder.appendAssistantMessage({ error: error.message });
        }
    }

    async runQuery(queryParameters, messageElement) {
        try {
            // Collect the current values from the editable fields
            const baseDnInput = messageElement.querySelector('input[name="base_dn"]');
            const searchFilterInput = messageElement.querySelector('input[name="search_filter"]');
            const searchAttributesInput = messageElement.querySelector('input[name="search_attributes"]');
            const limitInput = messageElement.querySelector('input[name="limit"]');
            const excludedAttributesInput = messageElement.querySelector('input[name="excluded_attributes"]');

            const base_dn = baseDnInput ? baseDnInput.value : queryParameters.base_dn;
            const search_filter = searchFilterInput ? searchFilterInput.value : queryParameters.search_filter;
            const search_attributes = searchAttributesInput ? searchAttributesInput.value : queryParameters.search_attributes;
            const limit = limitInput ? limitInput.value : queryParameters.limit;
            const excluded_attributes = excludedAttributesInput ? excludedAttributesInput.value : queryParameters.excluded_attributes;

            // Prepare query parameters
            const params = new URLSearchParams();
            params.append('base_dn', base_dn);
            params.append('search_filter', search_filter);
            params.append('search_attributes', search_attributes);
            params.append('limit', limit);
            params.append('excluded_attributes', excluded_attributes);

            // Run the query via the API endpoint
            const response = await fetch(`/active-directory/v1.0/query?${params.toString()}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                    // Add 'Authorization' header if required
                },
                credentials: 'same-origin' // Include cookies for authentication if necessary
            });

            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const result = await response.json();

            // Display the result
            this.uiBinder.appendQueryResultMessage(result, messageElement);

        } catch (error) {
            console.error('Error running query:', error);
            // Display error message
            this.uiBinder.appendQueryResultMessage({ error: error.message }, messageElement);
        }
    }


    confirmDeleteChatThread(threadId, threadTitle) {
        const modalId = 'deleteChatModal';

        // Use BaseAppUtils setModal to create the modal
        this.baseAppUtils.setModal(null, modalId, {
            title: 'Delete Chat',
            body: `<p>Are you sure you want to delete "<strong>${this.uiBinder.escapeHtml(threadTitle)}</strong>"?</p>`,
            footer: `
                <button type="button" class="btn btn-danger" id="confirmDeleteBtn">Delete</button>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            `,
            eventListeners: [
                {
                    selector: '#confirmDeleteBtn',
                    event: 'click',
                    handler: (event) => {
                        this.deleteChatThread(threadId, modalId);
                    }
                }
            ]
        });

        // Show the modal
        const modalInstance = new bootstrap.Modal(document.getElementById(modalId));
        modalInstance.show();
    }

    async deleteChatThread(threadId, modalId) {
        try {
            await this.baseAppUtils.restAjax('POST', '/myview/ajax/', {
                'action': 'delete_chat_thread',
                'thread_id': threadId
            });

            // Close the modal
            const modalElement = document.getElementById(modalId);
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            modalInstance.hide();

            // Refresh chat threads
            await this.loadChatThreads();

            // If the deleted thread was the current one, clear the messages
            if (this.currentThreadId === threadId) {
                this.currentThreadId = null;
                this.uiBinder.clearChatMessages();
            }

        } catch (error) {
            console.error('Error deleting chat thread:', error);
        }
    }

    static getInstance(uiBinder = UIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!App.instance) {
            App.instance = new App(uiBinder, baseAppUtils);
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
            this.chatList = document.getElementById('chat-list');
            this.newChatBtn = document.getElementById('new-chat-btn');
            this.loadingIndicator = this.createLoadingIndicator();
            this.autoRunToggle = document.getElementById('auto-run-toggle');
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

    appendUserMessage(message, timestamp = null) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'user-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.innerHTML = this.escapeHtml(message);

        messageElement.appendChild(messageContent);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }


    ntTimeToDate(ntTimeValue) {
        const ntTime = parseInt(ntTimeValue, 10);
        const ntEpoch = new Date(Date.UTC(1601, 0, 1));
        const millisecondsSinceNtEpoch = ntTime / 10000;
        const date = new Date(ntEpoch.getTime() + millisecondsSinceNtEpoch);
        const day = date.getUTCDate().toString().padStart(2, '0');
        const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
        const year = date.getUTCFullYear();
        return `${day}-${month}-${year}`;
    }

    dateToNtTime(dateString) {
        const [day, month, year] = dateString.split('-').map(Number);
        const date = new Date(Date.UTC(year, month - 1, day));
        const ntEpoch = new Date(Date.UTC(1601, 0, 1));
        const millisecondsSinceNtEpoch = date - ntEpoch;
        const ntTime = millisecondsSinceNtEpoch * 10000;
        return ntTime.toString();
    }

    appendAssistantMessage(message, timestamp = null) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'assistant-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');


// In appendAssistantMessage, after baseDnInput event listener
if (baseDnInput) {
    baseDnInput.addEventListener('input', async () => {
        const canonicalName = baseDnInput.value;
        if (canonicalName.length < 3) return; // Wait until the user has typed at least 3 characters

        // Prepare query parameters
        const params = new URLSearchParams();
        params.append('base_dn', 'DC=win,DC=dtu,DC=dk');
        params.append('search_filter', `(canonicalName=*${canonicalName}*)`);
        params.append('search_attributes', 'canonicalName');
        params.append('limit', '100');

        try {
            const response = await fetch(`/active-directory/v1.0/query?${params.toString()}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                },
                credentials: 'same-origin'
            });

            if (response.ok) {
                const result = await response.json();
                // Process the result to show suggestions
                this.showBaseDnSuggestions(baseDnInput, result);
            }
        } catch (error) {
            console.error('Error fetching base_dn suggestions:', error);
        }
    });
}

/// NOT SURE WHERE TO PUT THIS
// // Method to show suggestions
// showBaseDnSuggestions(inputElement, suggestions) {
//     // Implement a dropdown or autocomplete to display suggestions
//     // For simplicity, you can use a datalist
//     let dataList = inputElement.list;
//     if (!dataList) {
//         dataList = document.createElement('datalist');
//         dataList.id = 'baseDnSuggestions';
//         document.body.appendChild(dataList);
//         inputElement.setAttribute('list', 'baseDnSuggestions');
//     }
//     dataList.innerHTML = '';
//     suggestions.forEach(item => {
//         const option = document.createElement('option');
//         option.value = item['canonicalName'][0];
//         dataList.appendChild(option);
//     });
// }


// // Method to show suggestions
// showBaseDnSuggestions(inputElement, suggestions) {
//     // Implement a dropdown or autocomplete to display suggestions
//     // For simplicity, you can use a datalist
//     let dataList = inputElement.list;
//     if (!dataList) {
//         dataList = document.createElement('datalist');
//         dataList.id = 'baseDnSuggestions';
//         document.body.appendChild(dataList);
//         inputElement.setAttribute('list', 'baseDnSuggestions');
//     }
//     dataList.innerHTML = '';
//     suggestions.forEach(item => {
//         const option = document.createElement('option');
//         option.value = item['canonicalName'][0];
//         dataList.appendChild(option);
//     });
// }

        if (!message.error) {
            const buttonContainer = document.createElement('div');
            buttonContainer.classList.add('button-container');

            const runQueryBtn = document.createElement('button');
            runQueryBtn.textContent = 'Run Query';
            runQueryBtn.classList.add('run-query-btn');
            runQueryBtn.addEventListener('click', () => {
                App.getInstance().runQuery(message, messageElement);
            });

            const downloadExcelBtn = document.createElement('button');
            downloadExcelBtn.textContent = 'Download Excel';
            downloadExcelBtn.classList.add('download-excel-btn');
            downloadExcelBtn.addEventListener('click', () => {
                App.getInstance().downloadExcel(message, messageElement);
            });

            buttonContainer.appendChild(runQueryBtn);
            buttonContainer.appendChild(downloadExcelBtn);
            messageContent.appendChild(buttonContainer);
        }

        return messageElement; // Return the element for further manipulation
    }

    formatAssistantMessageContent(data) {
        let content = '';
        fields.forEach(field => {
            if (data[field]) {

                if (field === 'base_dn') {
                    content += `
                    <label>
                        <strong>${this.escapeHtml(field)} (Canonical Name):</strong>
                        <input type="text" name="${field}" value="${this.escapeHtml(data[field])}" />
                    </label><br>
                    <small>Distinguished Name: <code id="distinguished-name">${this.escapeHtml(this.canonicalToDistinguishedName(data[field]))}</code></small><br>
                    `;
                }


                else if (field === 'search_filter') {
                    const ntTimeMatch = this.parseSearchFilterForNtTime(data[field]);
                    if (ntTimeMatch) {
                        const ntTimeValue = ntTimeMatch.ntTimeValue;
                        const dateValue = this.ntTimeToDate(ntTimeValue);

                        content += `
                        <label>
                            <strong>${this.escapeHtml(field)}:</strong>
                            <input type="text" name="${field}" value="${this.escapeHtml(data[field])}" style="display:none;" />
                        </label><br>
                        <label>
                            <strong>pwdLastSet Date:</strong>
                            <input type="text" name="pwdLastSetDate" value="${this.escapeHtml(dateValue)}" />
                        </label><br>
                        <small>Actual search filter: <code class="actual-search-filter">${this.escapeHtml(data[field])}</code></small><br>
                        `;
                    } else {
                        content += `
                        <label>
                            <strong>${this.escapeHtml(field)}:</strong>
                            <input type="text" name="${field}" value="${this.escapeHtml(data[field])}" />
                        </label><br>`;
                    }
                } else {
                    content += `
                <label>
                    <strong>${this.escapeHtml(field)}:</strong>
                    <input type="text" name="${field}" value="${this.escapeHtml(data[field])}" />
                </label><br>`;
                }
            }
        });

        return content;
    }

    canonicalToDistinguishedName(canonicalName) {
        let parts = canonicalName.split('/');
        let domainParts = parts[0].split('.');
        let organizationalUnits = parts.slice(1).reverse();

        let distinguishedName = [];

        organizationalUnits.forEach(ou => {
            distinguishedName.push(`OU=${ou}`);
        });

        domainParts.forEach(dc => {
            distinguishedName.push(`DC=${dc}`);
        });

        return distinguishedName.join(',');
    }




    appendQueryResultMessage(result, messageElement) {
        let resultElement = messageElement.querySelector('.query-result');
        if (!resultElement) {
            resultElement = document.createElement('div');
            resultElement.classList.add('query-result');
            const resultContent = document.createElement('div');
            resultContent.classList.add('result-content');
            resultElement.appendChild(resultContent);
            messageElement.appendChild(resultElement);
        } else {
            // Clear previous content
            resultElement.querySelector('.result-content').innerHTML = '';
        }

        const resultContent = resultElement.querySelector('.result-content');

        if (result.error) {
            resultContent.textContent = `An error occurred: ${result.error}`;
        } else {
            // Display the result as formatted JSON
            resultContent.innerHTML = `<pre>${this.escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
        }

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

    clearChatMessages() {
        this.chatMessages.innerHTML = '';
    }

    populateChatThreads(threads) {
        this.chatList.innerHTML = '';
        threads.forEach(thread => {
            const threadItem = document.createElement('div');
            threadItem.classList.add('chat-thread-item');
            threadItem.dataset.threadId = thread.id;

            const threadTitle = document.createElement('span');
            threadTitle.classList.add('thread-title');
            threadTitle.textContent = thread.title;

            const deleteBtn = document.createElement('button');
            deleteBtn.classList.add('delete-chat-btn');
            deleteBtn.dataset.threadId = thread.id;
            deleteBtn.innerHTML = '&times;'; // X symbol

            threadItem.appendChild(threadTitle);
            threadItem.appendChild(deleteBtn);

            this.chatList.appendChild(threadItem);
        });
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
