# AI Ассистент с RAG и мульти-модельной архитектурой

Интеллектуальный веб-ассистент на Flask с поддержкой:
- Чат-интерфейса с историей сессий
- Переключения между моделями: Yandex GPT (облако) и локальные модели через Ollama
- RAG (Retrieval-Augmented Generation): загрузка PDF, TXT → семантический поиск → контекст в ответах
- Безопасной загрузки файлов и логирования

## 🛠 Технический стек
- **Бэкенд**: Flask 2.3+, Python 3.8+
- **База данных**: SQLite
- **Векторная БД**: FAISS
- **ML**: sentence-transformers, PyPDF2, python-docx
- **Фронтенд**: Jinja2, Bootstrap, Vanilla JS
- **Внешние сервисы**: Yandex Cloud GPT API, Ollama

---
## Создание файла .env
1. В корне проекта `ai-assistant-rag-multiple` создайте файл с именем: `.env`
2. Скопируйте и вставьте следующий текст:

```env
YANDEX_API_KEY=
YANDEX_FOLDER_ID=
TELEGRAM_BOT_TOKEN=
OLLAMA_BASE_URL=http://localhost:11434
LOCAL_MODEL_NAME=    #deepseek-r1:1.5b - пример имени "cmd: ollama list > NAME"

# Установка зависимостей
1. Откройте терминал в корне проекта ai-assistant-rag-multiple
2. Выполните команды по порядку:

# Создание виртуального окружения (≈10 сек)
python -m venv venv

# Активация виртуального окружения
# Для Windows:
venv\Scripts\activate

# Для Linux/Mac:
source venv/bin/activate

# Обновление pip (опционально)
python.exe -m pip install --upgrade pip

# Установка зависимостей (≈4 мин)
pip install -r requirements.txt

# Решение возможных проблем
Проблема с кодировкой (Windows)
Если возникают ошибки из-за смайликов в коде, выполните в PowerShell:

powershell
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
После этого перезапустите терминал.

# Запуск приложения
Убедитесь, что виртуальное окружение активировано (в терминале должно отображаться (venv))

Запустите файл run.py:

python run.py

После успешного запуска откройте браузер и перейдите по адресу: http://127.0.0.1:5000

# 🔧 Дополнительные настройки

Настройка Ollama
Убедитесь, что Ollama установлен и запущен

Проверьте доступные модели: ollama list

При необходимости скачайте модель: ollama pull имя_модели

Настройка Yandex Cloud, Создайте аккаунт в Yandex Cloud

Активируйте сервис Yandex GPT, Получите API ключ и Folder ID в консоли управления

❓ Часто задаваемые вопросы

Q: Приложение не запускается, что делать?
A: Проверьте:

Активировано ли виртуальное окружение

Заполнены ли все переменные в .env

Установлены ли все зависимости через requirements.txt

Q: Как добавить свою модель Ollama?
A: Измените переменную LOCAL_MODEL_NAME в файле .env на имя вашей модели

Q: Какие форматы файлов поддерживаются для загрузки?
A: PDF, TXT (файлы сохраняются в папку uploads/)
