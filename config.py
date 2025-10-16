# config.py
import os
from pathlib import Path

# Определяем корень проекта — папка, где лежит config.py
BASE_DIR = Path(__file__).parent.resolve()

# Создаём папку data
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{DATA_DIR}/database.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # === Paths ===
    FAISS_INDEX_PATH = str(DATA_DIR / "faiss_index")
    DOCUMENTS_FOLDER = str(DATA_DIR / "documents")
    Path(DOCUMENTS_FOLDER).mkdir(parents=True, exist_ok=True)

    # === Yandex Cloud GPT ===
    YANDEX_API_KEY = os.environ.get('YANDEX_API_KEY')
    YANDEX_FOLDER_ID = os.environ.get('YANDEX_FOLDER_ID')
    YANDEX_GPT_MODEL = 'yandexgpt-lite'

    # === Local LLM (Ollama) ===
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL') or 'http://localhost:11434'
    LOCAL_MODEL_NAME = os.environ.get('LOCAL_MODEL_NAME', 'local_llm') 

    # === Telegram Bot ===
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # === RAG ===
    EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50

    # === File upload ===
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

    print(" Загружен config.py из:", __file__)