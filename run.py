# run.py
import os
import sys
import threading
import logging
import argparse

# === ДОБАВЛЯЕМ КОРЕНЬ ПРОЕКТА В sys.path ===
# Это необходимо для корректного импорта модулей из app.*
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# =================================================

def main():
    parser = argparse.ArgumentParser(description='Запустить AI Assistant.')
    parser.add_argument('mode', choices=['web', 'bot', 'both'], nargs='?', default='both',
                        help='Режим запуска: web (Flask), bot (Telegram бот), both (Flask + Telegram бот)')
    args = parser.parse_args()

    # === ЗАПУСК FLASK ===
    if args.mode in ['web', 'both']:
        print("🚀 Запуск веб-сервера Flask...")
        if os.path.exists('.env'):
            from dotenv import load_dotenv
            load_dotenv()

        from app import create_app
        app = create_app()

        # Если запускаем оба — Flask в фоне
        if args.mode == 'both':
            flask_thread = threading.Thread(
                target=lambda: app.run(
                    host='0.0.0.0',
                    port=int(os.environ.get('PORT', 5000)),
                    debug=False,
                    use_reloader=False
                )
            )
            flask_thread.daemon = True
            flask_thread.start()
            print("✅ Flask запущен в фоне")
        else:
            # Если только Flask — запускаем в основном потоке
            app.run(
                host='0.0.0.0',
                port=int(os.environ.get('PORT', 5000)),
                debug=True
            )
    # === КОНЕЦ ЗАПУСКА FLASK ===

    # === ЗАПУСК TELEGRAM БОТА ===
    if args.mode in ['bot', 'both']:
        print("🚀 Запуск Telegram бота...")
        try:
            from app.bot.telegram_bot import run_bot
            # Запускаем бота в основном потоке (он блокирует выполнение)
            run_bot()
        except Exception as e:
            logging.error(f"❌ Ошибка запуска Telegram бота: {e}", exc_info=True)
            print(f"❌ ОШИБКА: Не удалось запустить Telegram бота: {e}")
            if args.mode == 'bot':
                # Если только бот — завершаем программу
                sys.exit(1)
            else:
                # Если both — продолжаем работу Flask
                print("⚠️ Telegram бот не запущен, но Flask работает.")
        # === КОНЕЦ ЗАПУСКА TELEGRAM БОТА ===

if __name__ == '__main__':
    main()