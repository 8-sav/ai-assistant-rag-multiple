# app/__init__.py
import os
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config


# Глобальные объекты
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Инициализация расширений
    db.init_app(app)

    # Настройка логирования
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler(
            'logs/ai_assistant.log',
            maxBytes=1024 * 1024 * 5,  # 5 MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('AI Assistant startup')

    # Регистрация Blueprints
    from app.routes import main_bp, model_bp, rag_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(model_bp, url_prefix='/api')
    app.register_blueprint(rag_bp, url_prefix='/api')

    # Централизованная обработка ошибок
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f"Server Error: {error}")
        return {'error': 'Internal server error'}, 500

    # Создание таблиц при первом запуске
    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app