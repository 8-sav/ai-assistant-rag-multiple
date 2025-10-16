# AI Ассистент с RAG и мульти-модельной архитектурой

Интеллектуальный веб-ассистент на Flask с поддержкой:
- **Чат-интерфейса** с историей сессий
- **Переключения между моделями**: Yandex GPT (облако) и Phi-3 (локально через Ollama)
- **RAG (Retrieval-Augmented Generation)**: загрузка PDF, DOCX, TXT → семантический поиск → контекст в ответах
- Безопасной загрузки файлов и логирования

---

## 🛠 Технический стек
- **Бэкенд**: Flask 2.3+, Python 3.8+
- **База данных**: SQLite
- **Векторная БД**: FAISS
- **ML**: `sentence-transformers`, `PyPDF2`, `python-docx`
- **Фронтенд**: Jinja2, Bootstrap, Vanilla JS
- **Внешние сервисы**: Yandex Cloud GPT API, Ollama (Phi-3)

---

## 🚀 Установка и запуск

### Требования
- Python 3.8+
- [Ollama](https://ollama.com/) с локальной моделью:  
  ```bash
  ollama run deepseek-r1:1.5b