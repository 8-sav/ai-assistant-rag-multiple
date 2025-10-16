# app/routes/model_bp.py

from flask import Blueprint, request, render_template, jsonify, current_app
from app.models import ChatSession, db

model_bp = Blueprint('model', __name__)

def get_llm_manager():
    if 'llm_manager' not in current_app.config:
        from app.services.llm_manager import LLMManager
        current_app.config['llm_manager'] = LLMManager(current_app.config)
    return current_app.config['llm_manager']

@model_bp.route('/models', methods=['GET'])  
def get_models():
    llm_manager = get_llm_manager()
    return jsonify(llm_manager.get_available_models())

@model_bp.route('/models-page')  
def models_page():
    return render_template('models.html')

@model_bp.route('/switch-model', methods=['POST'])
def switch_model():
    data = request.get_json()
    model_name = data.get('model_name')
    session_id = data.get('session_id')

    if not model_name or not session_id:
        return jsonify({'error': 'model_name and session_id are required'}), 400

    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    llm_manager = get_llm_manager()
    try:
        llm_manager.switch_model(model_name)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    session.model_used = model_name
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Model switched to {model_name}',
        'session_id': session_id
    })