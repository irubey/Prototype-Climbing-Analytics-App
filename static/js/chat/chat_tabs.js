class TabManager {
    constructor() {
        this.tabs = document.querySelectorAll('.app__nav-link');
        this.views = document.querySelectorAll('.app__panel');
        this.isTransitioning = false;
        this.setupEventListeners();
        this.initializeActiveTab();
    }

    setupEventListeners() {
        this.tabs.forEach(tab => {
            // Check if this is an internal tab (has data-view) or external link
            if (tab.hasAttribute('data-view')) {
                // Stop event propagation from child elements
                const icon = tab.querySelector('.app__nav-icon');
                if (icon) {
                    icon.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (!this.isTransitioning) {
                            this.handleTabClick(tab);
                        }
                    });
                }

                tab.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (!this.isTransitioning) {
                        this.handleTabClick(e.currentTarget);
                    }
                });
            }
        });
    }

    initializeActiveTab() {
        // Force clear any existing active states
        this.views.forEach(view => view.classList.remove('app__panel--active'));
        this.tabs.forEach(tab => tab.classList.remove('active'));

        // Determine which tab should be active
        const defaultTab = window.TEMPLATE_VARS.data_complete ? 'chat' : 'settings';
        const targetView = document.getElementById(`${defaultTab}_view`);
        const targetTab = document.querySelector(`[data-view="${defaultTab}"]`);

        if (targetView && targetTab) {
            targetView.classList.add('app__panel--active');
            targetTab.classList.add('active');
        }
    }

    handleTabClick(tab) {
        const targetId = tab.getAttribute('data-view');
        this.activateTab(targetId, true);
    }

    activateTab(viewId, animate = true) {
        if (this.isTransitioning) return;

        const targetView = document.getElementById(`${viewId}_view`);
        if (!targetView) return;

        this.isTransitioning = animate;

        // Update tab states
        this.tabs.forEach(t => {
            const isActive = t.getAttribute('data-view') === viewId;
            t.classList.toggle('active', isActive);
            t.setAttribute('aria-selected', isActive);
        });

        // Update view visibility
        requestAnimationFrame(() => {
            this.views.forEach(view => {
                const isTarget = view === targetView;
                if (animate) {
                    view.style.transition = 'opacity 0.3s ease';
                } else {
                    view.style.transition = 'none';
                }
                view.classList.toggle('app__panel--active', isTarget);
            });

            if (animate) {
                setTimeout(() => {
                    this.isTransitioning = false;
                }, 300);
            } else {
                this.isTransitioning = false;
            }
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.tabManager = new TabManager();
});

document.addEventListener('DOMContentLoaded', function () {
    const chatForm = document.getElementById('chat_form');
    const userPrompt = document.getElementById('user_prompt');
    const sendButton = chatForm.querySelector('.btn--send');
    const messageList = document.getElementById('message_list');
    const loadingIndicator = document.getElementById('loading_spinner');
    const messageTemplate = document.getElementById('message_template');
    const welcomeSection = document.querySelector('.chat__welcome');

    // Bind new chat button (which clears chat and resets the interface)
    const newChatButton = document.getElementById('new_chat');
    newChatButton.addEventListener('click', function () {
        if (confirm('Are you sure you want to start a new chat? This will clear the current conversation.')) {
            messageList.innerHTML = '';
            if (welcomeSection) {
                welcomeSection.style.display = 'block';
            }
            userPrompt.value = '';
            userPrompt.rows = 1;
            sendButton.disabled = true;
        }
    });

    // Auto-resize textarea
    function autoResizeTextarea(textarea) {
        const minRows = parseInt(textarea.dataset.minRows);
        const maxRows = parseInt(textarea.dataset.maxRows);
        textarea.style.height = 'auto';
        const rows = Math.min(
            Math.max(minRows, Math.ceil((textarea.scrollHeight - 20) / 24)),
            maxRows
        );
        textarea.rows = rows;
    }

    userPrompt.addEventListener('input', function () {
        sendButton.disabled = !this.value.trim();
        autoResizeTextarea(this);
    });

    chatForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const message = userPrompt.value.trim();
        if (!message) return;
        if (welcomeSection) {
            welcomeSection.style.display = 'none';
        }
        addMessage(message, true);
        userPrompt.value = '';
        userPrompt.rows = 1;
        sendButton.disabled = true;
        loadingIndicator.classList.add('loading-indicator--visible');
        try {
            const response = await fetch('/sage-chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({ message })
            });
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            addMessage(data.response, false);
        } catch (error) {
            console.error('Error:', error);
            addMessage('Sorry, I encountered an error. Please try again.', false);
        } finally {
            loadingIndicator.classList.remove('loading-indicator--visible');
        }
    });

    document.querySelectorAll('.prompt-button').forEach(button => {
        button.addEventListener('click', function () {
            const promptText = this.querySelector('.prompt-title').textContent;
            userPrompt.value = promptText;
            userPrompt.dispatchEvent(new Event('input'));
            chatForm.dispatchEvent(new Event('submit'));
        });
    });

    function addMessage(text, isUser) {
        const messageNode = messageTemplate.content.cloneNode(true);
        const messageDiv = messageNode.querySelector('.chat__message');
        const messageText = messageNode.querySelector('.chat__message-text');
        const messageTime = messageNode.querySelector('.chat__message-time');
        const messageAvatar = messageNode.querySelector('.chat__message-avatar img');

        if (isUser) {
            messageDiv.classList.add('chat__message--user');
            messageAvatar.src = '/static/images/user-avatar.png';
            messageAvatar.alt = 'User';
        } else {
            messageAvatar.src = '/static/images/brand/wizard-hat.svg';
            messageAvatar.alt = 'Sage';
        }

        messageText.textContent = text;
        messageTime.textContent = new Date().toLocaleTimeString();

        messageList.appendChild(messageNode);
        messageList.scrollTop = messageList.scrollHeight;
    }

    userPrompt.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.disabled) {
                chatForm.dispatchEvent(new Event('submit'));
            }
        }
    });
}); 