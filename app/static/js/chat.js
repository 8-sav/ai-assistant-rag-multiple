// app/static/js/chat.js

document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('chatForm')) {
        initChatPage();
    }
    if (document.getElementById('uploadForm')) {
        initUploadPage();
    }
    if (document.getElementById('modelsList')) {
        initModelsPage();
    }
});

// =============== ЧАТ ===============
function initChatPage() {
    const sessionId = window.chatConfig?.sessionId;
    if (!sessionId) {
        console.error('Session ID not found');
        return;
    }

    loadChatHistory(sessionId);
    loadModelsAndSetSelector(sessionId);
    setupChatForm(sessionId);

    updateRagStatus();  // Обновляем статус RAG
}

function loadChatHistory(sessionId) {
    const chatHistory = document.getElementById('chatHistory');
    fetch(`/api/session/${sessionId}/messages`)
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then(messages => {
            chatHistory.innerHTML = '';
            messages.forEach(msg => {
                const messageDiv = document.createElement('div');
                messageDiv.classList.add('message');

                if (msg.is_user) {
                    messageDiv.classList.add('user-message');
                    messageDiv.innerHTML = `
                        <div class="d-flex align-items-start">
                            <img src="/static/images/user-avatar.png" alt="User" class="avatar me-2" />
                            <div class="message-content">${msg.content}</div>
                        </div>
                    `;
                } else {
                    messageDiv.classList.add('ai-message');
                    if (msg.used_rag) messageDiv.classList.add('rag-used');

                    let avatarSrc = '/static/images/default-ai-avatar.png';

                    if (msg.model_used) {
                        if (msg.model_used === 'yandex_gpt') {
                            avatarSrc = '/static/images/yandex-avatar.png';
                        } else if (msg.model_used === 'local_llm') {
                            avatarSrc = '/static/images/local-avatar.png';
                        }
                    }

                    messageDiv.innerHTML = `
                        <div class="d-flex align-items-start">
                            <img src="${avatarSrc}" alt="AI" class="avatar me-2" />
                            <div class="message-content">${msg.content}</div>
                        </div>
                    `;
                }

                chatHistory.appendChild(messageDiv);
            });
            scrollToBottom();
        })
        .catch(err => {
            console.error('Failed to load chat history:', err);
            chatHistory.innerHTML = '<div class="text-center text-muted">Ошибка загрузки истории</div>';
        });
}

function loadModelsAndSetSelector(sessionId) {
    const modelSelect = document.getElementById('modelSelect');
    const currentModelEl = document.getElementById('currentModel');

    fetch('/api/models')
        .then(res => res.json())
        .then(models => {
            modelSelect.innerHTML = '';
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = model.display_name || model.name;
                if (!model.available) {
                    option.disabled = true;
                    option.classList.add('text-muted');
                }
                modelSelect.appendChild(option);
            });

            fetch(`/api/session/${sessionId}/info`)
                .then(res => res.json())
                .then(data => {
                    modelSelect.value = data.model_used;
                    const selectedModel = models.find(m => m.name === data.model_used);
                    if (selectedModel) {
                        currentModelEl.textContent = selectedModel.display_name || selectedModel.name;
                    } else {
                        currentModelEl.textContent = data.model_used;
                    }
                })
                .catch(err => {
                    console.error('Failed to load session info:', err);
                });
        })
        .catch(err => {
            console.error('Failed to load models:', err);
        });

    modelSelect.addEventListener('change', function () {
        const selectedModel = this.value;
        fetch('/api/switch-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: selectedModel, session_id: sessionId })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                fetch('/api/models')
                    .then(res => res.json())
                    .then(models => {
                        const model = models.find(m => m.name === selectedModel);
                        if (model) {
                            currentModelEl.textContent = model.display_name || model.name;
                        }
                    });
                alert('Модель успешно изменена!');
            }
        })
        .catch(err => {
            alert('Ошибка при смене модели');
            console.error(err);
        });
    });
}

function setupChatForm(sessionId) {
    const form = document.getElementById('chatForm');
    const userMessageInput = document.getElementById('userMessage');
    const chatHistory = document.getElementById('chatHistory');

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const messageText = userMessageInput.value.trim();
        if (!messageText) return;

        // Отображаем сообщение пользователя
        appendMessage(messageText, true, false, null);        

        // Очищаем поле
        userMessageInput.value = '';
        scrollToBottom();

        // --- НАЧАЛО: Добавляем индикатор ожидания ---
        const loadingIndicator = document.createElement('div');
        loadingIndicator.classList.add('message', 'ai-message', 'typing-indicator');
        loadingIndicator.id = 'loadingIndicator'; // Даем ID для легкого поиска/удаления
        loadingIndicator.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <span>Обработка запроса...</span>
            </div>
        `;
        chatHistory.appendChild(loadingIndicator);
        scrollToBottom();

        // Отправляем на сервер
        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText, session_id: sessionId })
        })
        .then(res => res.json())
        .then(data => {
            // --- НАЧАЛО: Удаляем индикатор ожидания ---
            const indicatorToRemove = document.getElementById('loadingIndicator');
            if (indicatorToRemove) {
                indicatorToRemove.remove();
            }
            //--- КОНЕЦ: Удаляем индикатор ожидания ---

            if (data.error) {
                appendMessage('❌ Ошибка: ' + data.error, false, false, null);
            } else {
                appendMessage(data.response, false, data.used_rag, data.model_used);
            }
            scrollToBottom();
        })
        .catch(err => {
            // --- НАЧАЛО: Удаляем индикатор ожидания и показываем ошибку ---
            const indicatorToRemove = document.getElementById('loadingIndicator');
            if (indicatorToRemove) {
                indicatorToRemove.remove();
            }
            appendMessage('❌ Не удалось получить ответ от сервера.', false, false, null);
            console.error(err);
            scrollToBottom();
            // --- КОНЕЦ: Удаляем индикатор ожидания и показываем ошибку ---
        });
    });
}

function appendMessage(text, isUser, usedRag, modelUsed) {
    const chatHistory = document.getElementById('chatHistory');

    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message');

    if (isUser) {
        messageDiv.classList.add('user-message');
        messageDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <img src="/static/images/user-avatar.png" alt="User" class="avatar me-2" />
                <div class="message-content">${text}</div>
            </div>
        `;
    } else {
        messageDiv.classList.add('ai-message');
        if (usedRag) messageDiv.classList.add('rag-used');

        let avatarSrc = '/static/images/default-ai-avatar.png';

        if (modelUsed) {
            if (modelUsed === 'yandex_gpt') {
                avatarSrc = '/static/images/yandex-avatar.png';
            } else if (modelUsed === 'local_llm') {
                avatarSrc = '/static/images/local-avatar.png';
            }
        }

        messageDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <img src="${avatarSrc}" alt="AI" class="avatar me-2" />
                <div class="message-content">${text}</div>
            </div>
        `;
    }

    chatHistory.appendChild(messageDiv);
}

function scrollToBottom() {
    const chatHistory = document.getElementById('chatHistory');
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// =============== УПРАВЛЕНИЕ ДОКУМЕНТАМИ ===============
function initUploadPage() {
    if (typeof window.uploadConfig === 'undefined') {
        window.uploadConfig = {
            inProgress: false
        };
    }

    const uploadForm = document.getElementById('uploadForm');
    const uploadProgress = document.getElementById('uploadProgress');
    const documentsList = document.getElementById('documentsList');
    const refreshBtn = document.getElementById('refreshDocuments');

    uploadForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (window.uploadConfig.inProgress) return;

        const fileInput = document.getElementById('documentFile');
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        window.uploadConfig.inProgress = true;
        uploadProgress.style.display = 'block';

        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => {
            if (res.status === 202) {
                return res.json().then(data => {
                    alert(`Документ "${data.filename}" загружен. Обработка начата.`);
                    loadDocuments();
                    fileInput.value = ''; // сброс
                });
            } else {
                return res.json().then(err => {
                    throw new Error(err.error || 'Неизвестная ошибка');
                });
            }
        })
        .catch(err => {
            alert('Ошибка загрузки: ' + err.message);
            console.error(err);
        })
        .finally(() => {
            window.uploadConfig.inProgress = false;
            uploadProgress.style.display = 'none';
        });
    });

    function loadDocuments() {
        fetch('/api/documents')
            .then(res => res.json())
            .then(docs => {
                if (docs.length === 0) {
                    documentsList.innerHTML = '<p class="text-muted">Нет загруженных документов.</p>';
                    return;
                }

                let html = '<div class="list-group">';
                docs.forEach(doc => {
                    const statusClass = doc.processed ? 'status-processed' : 'status-processing';
                    const statusText = doc.processed ? 'Обработан' : 'В обработке';
                    html += `
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${doc.filename}</strong><br>
                                <small>${(doc.file_size / 1024).toFixed(1)} KB • ${new Date(doc.uploaded_at).toLocaleString()}</small>
                            </div>
                            <div>
                                <span class="doc-status ${statusClass}">${statusText}</span>
                                <button class="btn btn-sm btn-danger btn-delete ms-2" data-id="${doc.id}">Удалить</button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                documentsList.innerHTML = html;

                // Назначаем обработчики удаления
                document.querySelectorAll('.btn-delete').forEach(btn => {
                    btn.addEventListener('click', function () {
                        const docId = this.getAttribute('data-id');
                        if (confirm('Удалить документ?')) {
                            fetch(`/api/documents/${docId}`, { method: 'DELETE' })
                                .then(res => res.json())
                                .then(() => loadDocuments())
                                .catch(err => {
                                    alert('Ошибка удаления');
                                    console.error(err);
                                });
                        }
                    });
                });
            })
            .catch(err => {
                documentsList.innerHTML = '<p class="text-danger">Ошибка загрузки списка документов.</p>';
                console.error(err);
            });
    }

    refreshBtn.addEventListener('click', loadDocuments);
    loadDocuments(); // первоначальная загрузка
}

// =============== УПРАВЛЕНИЕ МОДЕЛЯМИ ===============
function initModelsPage() {
    const modelsList = document.getElementById('modelsList');
    const currentSessionIdEl = document.getElementById('currentSessionId');
    const activeModelEl = document.getElementById('activeModel');
    const modelWarning = document.getElementById('modelWarning');

    // Получаем текущую сессию (в MVP — последнюю)
    fetch('/api/current-session')
        .then(res => res.json())
        .then(session => {
            currentSessionIdEl.textContent = session.id;
            activeModelEl.textContent = session.model_used;  // Обновляем модель
            loadModelsForPage(session.id);
        })
        .catch(() => {
            currentSessionIdEl.textContent = '—';
            activeModelEl.textContent = '—';
            modelsList.innerHTML = '<p class="text-danger">Не удалось загрузить сессию.</p>';
        });

    function loadModelsForPage(sessionId) {
        fetch('/api/models')
            .then(res => res.json())
            .then(models => {
                let html = '';
                models.forEach(model => {
                    const status = model.available ?
                        '<span class="text-success">✓ Доступна</span>' :
                        `<span class="text-warning">⚠️ Недоступна: ${model.reason || '—'}</span>`;
                    html += `
                        <div class="mb-3 p-2 border rounded ${!model.available ? 'model-unavailable' : ''}">
                            <strong>${model.display_name}</strong><br>
                            ${status}<br>
                            <button class="btn btn-sm ${model.available ? 'btn-outline-primary' : 'btn-outline-secondary'} mt-1"
                                    ${!model.available ? 'disabled' : ''}
                                    onclick="switchModel('${model.name}', ${sessionId})">
                                Использовать
                            </button>
                        </div>
                    `;
                });
                modelsList.innerHTML = html;
            })
            .catch(err => {
                modelsList.innerHTML = '<p class="text-danger">Ошибка загрузки моделей.</p>';
                console.error(err);
            });
    }

    // Глобальная функция для переключения
    window.switchModel = function(modelName, sessionId) {
        fetch('/api/switch-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: modelName, session_id: sessionId })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Обновляем отображение активной модели
                fetch('/api/models')
                    .then(res => res.json())
                    .then(models => {
                        const model = models.find(m => m.name === modelName);
                        if (model) {
                            activeModelEl.textContent = model.display_name || model.name;
                        }
                    });
                modelWarning.style.display = 'none';
                alert('Модель успешно изменена!');
            }
        })
        .catch(err => {
            alert('Ошибка при смене модели');
            console.error(err);
        });
    };
}

// =============== RAG СТАТУС ===============
function updateRagStatus() {
    const ragStatusEl = document.getElementById('ragStatus');
    fetch('/api/documents')
        .then(res => res.json())
        .then(docs => {
            const processedDocs = docs.filter(doc => doc.processed).length;
            if (processedDocs > 0) {
                ragStatusEl.textContent = 'доступен';
                ragStatusEl.classList.remove('text-muted');
                ragStatusEl.classList.add('text-success');
            } else {
                ragStatusEl.textContent = 'нет документов';
                ragStatusEl.classList.remove('text-success');
                ragStatusEl.classList.add('text-muted');
            }
        })
        .catch(err => {
            console.error('Failed to check RAG status:', err);
            ragStatusEl.textContent = 'ошибка';
            ragStatusEl.classList.remove('text-success');
            ragStatusEl.classList.add('text-danger');
        });
}