# app/services/llm_manager.py
import openai
import os
from flask import current_app

class YandexGPTProvider:
    def __init__(self, api_key: str, folder_id: str, model_name: str = 'yandexgpt-lite'):
        if not api_key or not folder_id:
            raise ValueError("Yandex API key and folder ID are required")
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://llm.api.cloud.yandex.net/v1",
        )
        self.model = f"gpt://{folder_id}/{model_name}"
        self.name = "yandex_gpt"

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.error(f"Yandex GPT API error: {e}")
            raise RuntimeError(f"Yandex GPT request failed: {str(e)}")


class LocalLLMProvider:
    def __init__(self, base_url: str, model_name: str):
        self.client = openai.OpenAI(
            base_url=f"{base_url.rstrip('/')}/v1",
            api_key="ollama"
        )
        self.model_name = model_name
        self.name = "local_llm"

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.error(f"Local LLM (Ollama) error: {e}")
            raise RuntimeError(f"Local LLM request failed: {str(e)}")


class LLMManager:    
    def __init__(self, config):
        self.config = config
        self.providers = {}
        self.current_provider = None

        # Yandex GPT
        yandex_key = config.get('YANDEX_API_KEY')
        yandex_folder = config.get('YANDEX_FOLDER_ID')
        if yandex_key and yandex_folder:
            self.providers['yandex_gpt'] = YandexGPTProvider(
                api_key=yandex_key,
                folder_id=yandex_folder,
                model_name=config.get('YANDEX_GPT_MODEL', 'yandexgpt-lite')
            )
        else:
            current_app.logger.warning("Yandex GPT not configured")

        # Local LLM
        ollama_url = config.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        local_model = config.get('LOCAL_MODEL_NAME', 'local_llm')  # ← Теперь 'local_llm' по умолчанию
        self.providers['local_llm'] = LocalLLMProvider(
            base_url=ollama_url,
            model_name=local_model
        )

        # Выбор по умолчанию
        self.switch_model('yandex_gpt' if 'yandex_gpt' in self.providers else 'local_llm')

    def switch_model(self, model_name: str):
        if model_name not in self.providers:
            available = list(self.providers.keys())
            raise ValueError(f"Model '{model_name}' not available. Available: {available}")
        self.current_provider = self.providers[model_name]

    def generate_response(self, prompt: str, use_rag: bool = False, rag_context: str = "", chat_history: list = None) -> dict:
        if use_rag and rag_context.strip():
            full_prompt = (
                "Используй следующий контекст для ответа на вопрос. "
                "Если контекст не содержит ответа, скажи, что не знаешь.\n\n"
                f"Контекст:\n{rag_context}\n\n"
                f"Вопрос:\n{prompt}\n\n"
                "Ответ:"
            )
        else:
            if chat_history and isinstance(chat_history, list):
                history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
                full_prompt = (
                    "Ты полезный ассистент. Вот история нашего диалога:\n"
                    f"{history_text}\n\n"
                    f"Новый вопрос пользователя:\n{prompt}\n\n"
                    "Ответ:"
                )

            full_prompt = prompt

        if self.current_provider is None:
            raise RuntimeError("No LLM provider selected")        
        try:
            response_text = self.current_provider.generate(full_prompt)
            model_name = getattr(self.current_provider, 'name', 'unknown_model')
            return {
                'response': response_text,
                'model_used': self.current_provider.name # <-- Добавляем имя модели
            }
        except Exception as e:
            current_app.logger.error(f"LLM generation error: {e}")
            raise RuntimeError(f"Failed to generate response: {str(e)}")

    def get_available_models(self) -> list:
        models = []
        if 'yandex_gpt' in self.providers:
            models.append({
                'name': 'yandex_gpt',
                'display_name': 'Yandex GPT (Cloud)',
                'available': True
            })
        if 'local_llm' in self.providers:
            local_name = self.config.get('LOCAL_MODEL_NAME', 'local')
            models.append({
                'name': 'local_llm',
                'display_name': f'{local_name} (Local)',
                'available': True
            })
        return models
    