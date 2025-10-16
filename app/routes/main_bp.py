# app/routes/main_bp.py
from flask import Blueprint, render_template, request, jsonify, current_app
from app.models import db, ChatSession, Message, Document
from app import db
import threading

main_bp = Blueprint('main', __name__)

def get_llm_manager():
    if 'llm_manager' not in current_app.config:
        from app.services.llm_manager import LLMManager
        current_app.config['llm_manager'] = LLMManager(current_app.config)
    return current_app.config['llm_manager']

def get_rag_engine():
    if 'rag_engine' not in current_app.config:
        from app.services.vector_db import VectorDB
        from app.services.rag_engine import RAGEngine
        config = current_app.config
        vector_db = VectorDB(
            index_path=config['FAISS_INDEX_PATH'],
            embedding_model_name=config['EMBEDDING_MODEL']
        )
        vector_db.initialize_index()
        rag_engine = RAGEngine(
            vector_db=vector_db,
            embedding_model_name=config['EMBEDDING_MODEL'],
            chunk_size=config['CHUNK_SIZE'],
            chunk_overlap=config['CHUNK_OVERLAP']
        )
        current_app.config['rag_engine'] = rag_engine
    return current_app.config['rag_engine']

@main_bp.route('/')
def index():
    # Получаем или создаём дефолтного пользователя и сессию (для однопользовательского режима)
    from app.models import User
    user = User.query.first()
    if not user:
        user = User(username='default')
        db.session.add(user)
        db.session.commit()

    # Получаем последнюю сессию или создаём новую
    session = ChatSession.query.filter_by(user_id=user.id).order_by(ChatSession.created_at.desc()).first()
    if not session:
        session = ChatSession(user_id=user.id, title="Новая сессия")
        db.session.add(session)
        db.session.commit()

    return render_template('chat.html', session_id=session.id)

@main_bp.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message_text = data.get('message', '').strip()
    session_id = data.get('session_id')

    if not message_text or not session_id:
        return jsonify({'error': 'Message and session_id are required'}), 400

    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    # Сохраняем сообщение пользователя
    user_message = Message(
        session_id=session_id,
        content=message_text,
        is_user=True,
        used_rag=False
    )
    db.session.add(user_message)

    # Проверяем, есть ли обработанные документы → включаем RAG
    has_processed_docs = Document.query.filter_by(processed=True).count() > 0
    rag_context = ""
    used_rag = False

    if has_processed_docs:
        rag_engine = get_rag_engine()
        rag_context = rag_engine.augment_prompt(message_text, k=3)
        used_rag = bool(rag_context.strip())

    # Переключаем LLM на модель из сессии
    llm_manager = get_llm_manager()
    try:
        llm_manager.switch_model(session.model_used)        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Генерация ответа
    try:
        response_dict = llm_manager.generate_response(
            prompt=message_text,
            use_rag=used_rag,
            rag_context=rag_context
        )
        # Извлекаем текст ответа из словаря
        response_text_to_save = response_dict['response']
        # (Опционально) Извлекаем имя модели
        model_used = response_dict.get('model_used', 'unknown')
    except Exception as e:
        current_app.logger.error(f"LLM generation error: {e}")
        return jsonify({'error': 'Failed to generate response'}), 500

    # Сохраняем ответ ассистента
    ai_message = Message(
        session_id=session_id,
        content=response_text_to_save,
        is_user=False,
        used_rag=used_rag,
        model_used=model_used
    )
    db.session.add(ai_message)
    db.session.commit()

    return jsonify({
        'response': response_text_to_save,
        'used_rag': used_rag,
        'model_used': session.model_used
    })
@main_bp.route('/api/current-session', methods=['GET'])
def get_current_session():
    from app.models import User, ChatSession
    user = User.query.first()
    if not user:
        # Создаём дефолтного пользователя, если нет
        user = User(username='default')
        db.session.add(user)
        db.session.commit()

    # Получаем последнюю сессию или создаём новую
    session = ChatSession.query.filter_by(user_id=user.id).order_by(ChatSession.created_at.desc()).first()
    if not session:
        session = ChatSession(user_id=user.id, title="Новая сессия")
        db.session.add(session)
        db.session.commit()

    return jsonify({
        'id': session.id,
        'title': session.title,
        'model_used': session.model_used,  
        'created_at': session.created_at.isoformat()
    })
@main_bp.route('/api/session/<int:session_id>/info', methods=['GET'])
def get_session_info(session_id):
    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify({
        'id': session.id,
        'title': session.title,
        'model_used': session.model_used,
        'created_at': session.created_at.isoformat()
    })
@main_bp.route('/api/session/<int:session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    messages = Message.query.filter_by(session_id=session_id).order_by(Message.timestamp).all()
    result = []
    for msg in messages:
        result.append({
            'id': msg.id,
            'content': msg.content,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.isoformat(),
            'used_rag': msg.used_rag,
            'model_used': msg.model_used
        })
    return jsonify(result)