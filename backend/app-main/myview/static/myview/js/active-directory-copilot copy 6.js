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
            if (threadItem) {
                const threadId = threadItem.dataset.threadId;
                this.loadChatMessages(threadId);
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
                    this.uiBinder.appendAssistantMessage(message.content, message.timestamp);
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
            this.uiBinder.appendAssistantMessage(JSON.stringify(assistantResponse, null, 2));

        } catch (error) {
            console.error('Error sending message:', error);
            this.uiBinder.hideLoading();
            this.uiBinder.appendAssistantMessage(`An error occurred: ${error}`);
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

    appendAssistantMessage(message, timestamp = null) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'assistant-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');

        try {
            const data = JSON.parse(message);
            messageContent.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        } catch (e) {
            messageContent.innerHTML = message;
        }

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

    clearChatMessages() {
        this.chatMessages.innerHTML = '';
    }

    populateChatThreads(threads) {
        this.chatList.innerHTML = '';
        threads.forEach(thread => {
            const threadItem = document.createElement('div');
            threadItem.classList.add('chat-thread-item');
            threadItem.dataset.threadId = thread.id;
            threadItem.textContent = thread.title;
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
