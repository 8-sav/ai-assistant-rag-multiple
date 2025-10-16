# app/models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Импортируем db из app/__init__.py через циклический импорт
from app import db

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, default='Новая сессия')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    model_used = db.Column(db.String(50), default='yandex_gpt')  # 'yandex_gpt' или 'local'

    messages = db.relationship('Message', backref='session', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ChatSession {self.id}>'


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, nullable=False)  # True — от пользователя, False — от ассистента
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    used_rag = db.Column(db.Boolean, default=False)  # использовался ли RAG при генерации ответа
    model_used = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<Message {"User" if self.is_user else "AI"}>'


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # в байтах
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Document {self.filename}>'