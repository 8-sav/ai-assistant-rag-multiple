# app/routes/rag_bp.py

import os
import threading
import magic  
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.models import db, Document

rag_bp = Blueprint('rag', __name__)

# Поддерживаемые MIME-типы (magic возвращает MIME)
ALLOWED_MIME_TYPES = {
    'text/plain',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

def get_rag_engine():
    """
    Ленивая инициализация RAGEngine с кэшированием в app.config.
    """
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

def process_document_background(doc_id, file_path):
    from app import create_app  
    app = create_app()

    with app.app_context():
        try:
            from app.models import db, Document  
            from app.services.rag_engine import RAGEngine  
            from flask import current_app

            current_app.logger.info(f"Starting background processing for doc {doc_id} at {file_path}")
            rag_engine = get_rag_engine()
            current_app.logger.info(f"RAG engine loaded for doc {doc_id}")
            success = rag_engine.add_document(file_path, doc_id)
            current_app.logger.info(f"RAG engine add_document returned: {success}")

            # Обновляем статус в БД
            doc = Document.query.get(doc_id)
            if doc:
                doc.processed = success
                db.session.commit()
                if success:
                    current_app.logger.info(f"Document {doc_id} processed successfully")
                else:
                    current_app.logger.warning(f"Failed to process document {doc_id}")
        except Exception as e:
            current_app.logger.error(f"Background processing error for doc {doc_id}: {e}", exc_info=True)
            # Помечаем как необработанный, если ошибка
            doc = Document.query.get(doc_id)
            if doc:
                doc.processed = False
                db.session.commit()

@rag_bp.route('/')  # <-- HTML-маршрут для страницы "Документы"
def upload_page():
    """
    Возвращает HTML-шаблон для загрузки и управления документами.
    Это позволяет использовать url_for('rag.upload_page') в base.html.
    """
    return render_template('upload.html')

@rag_bp.route('/upload', methods=['POST'])
def upload_document():
    """
    Загружает файл, проверяет тип и размер, сохраняет на диск,
    создаёт запись в БД и запускает фоновую обработку.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    # Безопасное имя файла
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    # Проверка размера файла
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > current_app.config['MAX_CONTENT_LENGTH']:
        return jsonify({'error': 'File too large'}), 413

    # Проверка типа файла по содержимому (magic bytes) с помощью magic
    file_data = file.read(2048)  # читаем начало файла
    file.seek(0)  # возвращаем указатель в начало
    try:
        mime_type = magic.from_buffer(file_data, mime=True)
    except magic.MagicException:
        return jsonify({'error': 'Could not detect file type'}), 400

    if mime_type not in ALLOWED_MIME_TYPES:
        return jsonify({'error': f'Unsupported file type: {mime_type}'}), 400

    # Сохраняем файл
    documents_folder = current_app.config['DOCUMENTS_FOLDER']
    file_path = os.path.join(documents_folder, filename)

    # Избегаем коллизий имён
    counter = 1
    original_name = filename
    while os.path.exists(file_path):
        name, ext = os.path.splitext(original_name)
        filename = f"{name}_{counter}{ext}"
        file_path = os.path.join(documents_folder, filename)
        counter += 1

    file.save(file_path)

    # Создаём запись в БД
    doc = Document(
        filename=original_name,
        file_path=file_path,
        file_size=file_size
    )
    db.session.add(doc)
    db.session.commit()

    # Запускаем фоновую обработку
    thread = threading.Thread(
        target=process_document_background,
        args=(doc.id, file_path)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'doc_id': doc.id,
        'filename': original_name,
        'status': 'uploaded, processing started'
    }), 202

@rag_bp.route('/documents', methods=['GET'])
def list_documents():
    """
    Возвращает список всех загруженных документов с флагом processed.
    """
    docs = Document.query.order_by(Document.uploaded_at.desc()).all()
    result = [{
        'id': d.id,
        'filename': d.filename,
        'file_size': d.file_size,
        'uploaded_at': d.uploaded_at.isoformat(),
        'processed': d.processed
    } for d in docs]
    return jsonify(result)

@rag_bp.route('/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """
    Удаляет документ из БД и с диска.
    FAISS не поддерживает удаление векторов в IndexFlatL2, поэтому
    индекс остаётся, но документ удаляется из БД и с диска.
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    # Удаляем файл с диска
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError as e:
            current_app.logger.warning(f"Failed to delete file {doc.file_path}: {e}")

    # Удаляем запись из БД
    db.session.delete(doc)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Document deleted'})

@rag_bp.route('/stats', methods=['GET'])
def rag_stats():
    """
    Возвращает статистику по RAG: количество документов, обработанных и др.
    """
    total_docs = Document.query.count()
    processed_docs = Document.query.filter_by(processed=True).count()

    return jsonify({
        'total_documents': total_docs,
        'processed_documents': processed_docs,
        'faiss_index_path': current_app.config['FAISS_INDEX_PATH'],
        'embedding_model': current_app.config['EMBEDDING_MODEL']
    })