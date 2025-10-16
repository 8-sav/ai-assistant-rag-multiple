# app/bot/telegram_bot.py
"""
Telegram-бот для AI Ассистента.
Позволяет пользователю выбирать между Yandex GPT и локальной моделью (Ollama),
вести диалог, сменить модель, сбросить историю и т.д.
"""

# === ДОБАВЛЯЕМ КОРЕНЬ ПРОЕКТА В sys.path ===
# Это необходимо для корректного импорта модулей из app.* и config.py
import sys
import os

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ФОРМАТИРОВАНИЯ ===
def get_model_emoji(model_name: str) -> str:
    """Возвращает эмодзи для модели."""
    emoji_map = {
        'yandex_gpt': '☁️',  # Облако для Yandex GPT
        'local_llm': '💻'    # Компьютер для локальной модели
    }
    return emoji_map.get(model_name, '🤖')  # По умолчанию робот

def format_response_with_model(model_display_name: str, model_name: str, response: str) -> str:
    """Форматирует ответ с указанием модели и эмодзи."""
    emoji = get_model_emoji(model_name)
    return f"{emoji} *{model_display_name}*\n\n{response}"
# =================================================


# Получаем путь к корню проекта.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# =================================================
from config import Config
# === ИМПОРТЫ ===
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Импортируем конфигурацию и LLMManager из проекта
from config import Config
from app.services.llm_manager import LLMManager
# ===============

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# =============================
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
# === СОСТОЯНИЯ ДЛЯ ConversationHandler ===
# Определяем состояния диалога
SELECTING_MODEL, CHATTING, CHANGING_MODEL = range(3)
# ========================================

# === ХРАНЕНИЕ СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ===
# Для MVP используем глобальный словарь.
# {user_id: {'llm_manager': LLMManager_instance, 'model': 'yandex_gpt'/'local_llm', 'history': []}}
user_states = {}
# ======================================

# === ХЭНДЛЕРЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправляет приветственное сообщение и предлагает выбрать модель."""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} начал диалог (/start).")

    # Инициализируем LLMManager для этого пользователя
    try:
        config_dict = {key: getattr(Config, key) for key in dir(Config) if not key.startswith('__')}
        llm_manager = LLMManager(config_dict) # ✅ Передаём СЛОВАРЬ
        # Сохраняем менеджер и пустую историю в состоянии пользователя
        user_states[user_id] = {
            'llm_manager': llm_manager,
            'model': None,
            'history': [] # Для MVP: список сообщений в формате {'role': '...', 'content': '...'}
        }
        logger.info(f"LLMManager создан для пользователя {user_id}.")
    except Exception as e:
        logger.error(f"Ошибка создания LLMManager для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Извините, произошла внутренняя ошибка. Попробуйте позже.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Привет! Я AI-ассистент.\n\nВыбери модель для общения:",
        reply_markup=get_model_selection_keyboard()
    )
    return CHANGING_MODEL

def get_model_selection_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для выбора модели."""
    keyboard = [
        ['Yandex GPT (Cloud)'],
        ['Local LLM (Ollama)']
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор модели пользователем."""
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"Пользователь {user_id} выбрал: {text}")
    user_state = user_states.get(user_id)
    
    if not user_state or not user_state.get('llm_manager'):
        logger.warning(f"Пользователь {user_id} без состояния пытался выбрать модель.")
        await update.message.reply_text(
            "⚠️ Ошибка состояния. Начни сначала с /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    llm_manager = user_state['llm_manager']
    available_models = {m['name'] for m in llm_manager.get_available_models()}
    # Сопоставляем текст с внутренним именем модели
    model_map = {
        'Yandex GPT (Cloud)': 'yandex_gpt',
        'Local LLM (Ollama)': 'local_llm'
    }
    model_name = model_map.get(text)

    if not model_name:
        logger.warning(f"Пользователь {user_id} выбрал неизвестную модель: {text}")
        await update.message.reply_text(
            "❓ Неверный выбор. Пожалуйста, выбери модель из списка.",
            reply_markup=get_model_selection_keyboard()
        )
        return SELECTING_MODEL

     
    # Проверяем, доступна ли модель
    available_models = {m['name'] for m in llm_manager.get_available_models()}
    if model_name not in available_models:
        logger.warning(f"Пользователь {user_id} выбрал недоступную модель: {model_name}")
        await update.message.reply_text(
            f"🚫 Модель '{text}' в данный момент недоступна.",
            reply_markup=get_model_selection_keyboard()
        )
        return CHANGING_MODEL

    try:
        # Переключаем LLMManager на выбранную модель
        llm_manager.switch_model(model_name)
        user_state['model'] = model_name
        # Сбрасываем историю при смене модели
        user_state['history'] = []
        logger.info(f"Пользователь {user_id} успешно переключился на модель: {model_name}")

    
        # Получаем отображаемое имя модели для сообщения пользователю
        model_info = next((m for m in llm_manager.get_available_models() if m['name'] == model_name), {})
        display_name = model_info.get('display_name', model_name)
        
        welcome_msg = (
            f"✅ Отлично! Ты выбрал модель: <b>{display_name}</b>.\n\n"
            "Теперь ты можешь задавать вопросы!\n"
            "Доступные команды:\n"
            "/model - сменить модель\n"
            "/reset - сбросить историю\n"
            "/help - помощь"
        )
        await update.message.reply_text(
            welcome_msg,
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove() # Убираем клавиатуру выбора
        )
        return CHATTING
    except Exception as e:
        logger.error(f"Ошибка переключения модели для пользователя {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка при выборе модели. Попробуй начать сначала с /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


async def change_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора новой модели через /model."""
    user_id = update.effective_user.id
    user_state = user_states.get(user_id)
    
    if not user_state or not user_state.get('llm_manager'):
        await update.message.reply_text("⚠️ Пожалуйста, сначала начни с /start.")
        return ConversationHandler.END

    llm_manager = user_state.get('llm_manager')
    if not llm_manager:
        await update.message.reply_text("⚠️ Ошибка состояния. Начни сначала с /start.")
        return ConversationHandler.END

    text = update.message.text
    model_map = {
        'Yandex GPT (Cloud)': 'yandex_gpt',
        'Local LLM (Ollama)': 'local_llm'
    }
    model_name = model_map.get(text)


    if not model_name:
        logger.warning(f"Пользователь {user_id} выбрал неизвестную модель: {text}")
        await update.message.reply_text(
            "❓ Неверный выбор. Пожалуйста, выбери модель из списка.",
            reply_markup=get_model_selection_keyboard()
        )
        return CHANGING_MODEL
    
    # Проверяем, доступна ли модель
    available_models = {m['name'] for m in llm_manager.get_available_models()}
    if model_name not in available_models:
        logger.warning(f"Пользователь {user_id} выбрал недоступную модель: {model_name}")
        await update.message.reply_text(
            f"🚫 Модель '{text}' в данный момент недоступна.",
            reply_markup=get_model_selection_keyboard()
        )
        return CHANGING_MODEL

    try:
        user_state['llm_manager'].switch_model(model_name)
        user_state['model'] = model_name
        user_state['history'] = [] # Сбрасываем историю
        logger.info(f"Пользователь {user_id} успешно переключился на модель: {model_name}")
        model_info = next((m for m in user_state['llm_manager'].get_available_models() if m['name'] == model_name), {})
        display_name = model_info.get('display_name', model_name)
        await update.message.reply_text(
            f"✅ Модель успешно изменена на: <b>{display_name}</b>",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove()
        )
        
        return CHATTING
    except Exception as e:
        logger.error(f"Ошибка смены модели для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Ошибка при смене модели. Попробуй позже.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения пользователя во время чата."""
    user_id = update.effective_user.id    
    user_state = user_states.get(user_id)
    user_message_text = update.message.text
    logger.info(f"Получено сообщение от пользователя {user_id}: {user_message_text}")
        
    # Проверяем, что пользователь выбрал модель
    if not user_state or not user_state.get('model'):
        logger.info(f"Пользователь {user_id} ещё не выбрал модель.")
        await update.message.reply_text("ℹ️ Пожалуйста, сначала выбери модель с помощью /start.")
        return

    llm_manager = user_state['llm_manager']
    model_name = user_state['model']
    chat_history = user_state['history']

    # --- Отправляем сообщение "печатает..." ---
    await update.message.chat.send_action("typing")
    # -------------------------------------------

    try:
        # --- Подготовка контекста из истории ---
        MAX_HISTORY_PAIRS = 5 # 5 пар вопрос-ответ
        recent_history = chat_history[-(MAX_HISTORY_PAIRS * 2):] if len(chat_history) > MAX_HISTORY_PAIRS * 2 else chat_history

        # Добавляем новое сообщение пользователя в историю
        chat_history.append({"role": "user", "content": user_message_text})

        # --- Генерация ответа с историей ---
        logger.info(f"Отправка запроса в LLM ({model_name}) для пользователя {user_id} с историей...")
        result_dict = llm_manager.generate_response(
            prompt=user_message_text,
            chat_history=chat_history 
        )

        bot_response = result_dict.get('response', 'Извините, не удалось сгенерировать ответ.')
        model_used_final = result_dict.get('model_used', model_name)
        logger.info(f"Ответ от LLM ({model_used_final}) для пользователя {user_id} получен (длина: {len(bot_response)} символов).")

        # Добавляем ответ ассистента в историю
        chat_history.append({"role": "assistant", "content": bot_response})

        # === ФОРМАТИРУЕМ ОТВЕТ С УКАЗАНИЕМ МОДЕЛИ И ЭМОДЗИ ===
        # Получаем отображаемое имя модели
        model_info = next((m for m in llm_manager.get_available_models() if m['name'] == model_used_final), {})
        display_name = model_info.get('display_name', model_used_final)
        
        # Форматируем финальное сообщение
        final_response = format_response_with_model(display_name, model_used_final, bot_response)
        
        # Отправляем ответ
        await update.message.reply_text(final_response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка генерации для пользователя {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "😔 Извини, произошла ошибка при обработке твоего запроса. Попробуй еще раз."
        )

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /model — предлагает сменить модель."""
    user_id = update.effective_user.id
    user_state = user_states.get(user_id)
    
    if not user_state or not user_state.get('llm_manager'):
        await update.message.reply_text("⚠️ Пожалуйста, сначала начни с /start.")
        return

    await update.message.reply_text(
        "🔁 Выбери новую модель:",
        reply_markup=get_model_selection_keyboard()
    )
    return CHANGING_MODEL
    

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /reset — сбрасывает историю чата."""
    user_id = update.effective_user.id
    user_state = user_states.get(user_id)
    
    if not user_state or not user_state.get('model'):
        await update.message.reply_text("⚠️ Пожалуйста, сначала выбери модель с помощью /start.")
        return

    # Сбрасываем историю
    user_state['history'] = []
    await update.message.reply_text("🔄 История чата сброшена. Начни новый диалог!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help — показывает список команд."""
    help_text = (
        "⚙️ <b>Доступные команды:</b>\n\n"
        "/start - Начать новый диалог и выбрать модель\n"
        "/model - Сменить активную модель\n"
        "/reset - Сбросить историю текущего чата\n"
        "/help - Показать это сообщение\n\n"
        "Просто отправь мне текстовое сообщение, и я отвечу!"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /cancel. Завершает диалог."""
    user_id = update.effective_user.id
    if user_id in user_states:
        del user_states[user_id]
    logger.info(f"Пользователь {user_id} отменил диалог (/cancel).")
    await update.message.reply_text(
        "⏹ Диалог отменен. Начни сначала с /start.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ===================

# === ФУНКЦИЯ ЗАПУСКА ===

def run_bot() -> None:
    """Функция для запуска Telegram-бота."""
    logger.info("Инициализация Telegram-бота...")

    # 1. Получаем токен из конфигурации
    TOKEN = Config.TELEGRAM_BOT_TOKEN

    # 2. Проверяем, установлен ли токен
    if not TOKEN or not isinstance(TOKEN, str) or TOKEN.strip() == '' or 'your_telegram_bot_token_here' in TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN не установлен корректно в .env или config.py")
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА!")
        print("TELEGRAM_BOT_TOKEN не найден или некорректен.")
        print("Проверь файл .env и config.py.")
        print("========================\n")
        return # Завершаем выполнение функции

    logger.info("TELEGRAM_BOT_TOKEN загружен успешно.")

    # 3. Создаем приложение бота
    try:
        application = Application.builder().token(TOKEN).build()
        logger.info("Application (ApplicationBuilder) создано.")
    except Exception as e:
        logger.critical(f"Ошибка создания Application: {e}")
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА!")
        print(f"Не удалось инициализировать бота: {e}")
        print("========================\n")
        return

    # 4. Определяем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_model)],
            CHATTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CommandHandler('model', model_command),
                CommandHandler('reset', reset_command),
                CommandHandler('help', help_command),
            ],
            CHANGING_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_model_command)]

        },
        fallbacks=[CommandHandler('cancel', cancel)],
        
    )

    # 5. Добавляем обработчики в приложение
    application.add_handler(conv_handler)
    # Добавляем глобальные команды (работают в любом состоянии)
    application.add_handler(CommandHandler('model', model_command))
    application.add_handler(CommandHandler('reset', reset_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cancel', cancel)) # Добавляем /cancel вне ConversationHandler тоже
    
    # 6. Запускаем polling
    logger.info("Telegram бот готов к запуску polling...")
    print("\n🤖 Telegram бот запущен. Нажми Ctrl+C для остановки.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# =======================

# === ТОЧКА ВХОДА ДЛЯ СКРИПТА ===
# Позволяет запускать файл напрямую: python app/bot/telegram_bot.py
if __name__ == '__main__':
    run_bot()
# =================================