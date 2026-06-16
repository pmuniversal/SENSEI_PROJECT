"""
main.py (внутри пакета bot) — Точка входа бота Sensei
======================================================

ПРОСТЫМИ СЛОВАМИ:
Это «пульт запуска». Здесь всё собирается вместе:
  1. Создаются нужные папки.
  2. Создаётся Telegram-бот с токеном из настроек.
  3. Подключаются обработчики (текст, голос, команды).
  4. Запускаются фоновые процессы (напоминания и бэкапы).
  5. Бот начинает слушать сообщения.
"""

import threading

import telebot

from bot import config
from bot.database import db  # импорт создаёт подключение и таблицы
from bot.utils.folders import ensure_folders
from bot.handlers import text, voice, commands
from bot.services.reminders import reminder_loop
from bot.services.backup import backup_loop
from bot.services.telegram_backup import backup_offsite_loop
from bot.services.proactive import proactive_loop


def main() -> None:
    """Собирает и запускает бота."""
    # 1. Убедиться, что папки данных существуют
    ensure_folders()

    # 2. Создать бота (токен берётся из config -> .env)
    bot = telebot.TeleBot(config.TELEGRAM_TOKEN)

    # 3. Подключить обработчики сообщений
    text.register(bot)
    voice.register(bot)
    commands.register(bot)

    # 4. Запустить фоновые процессы (демоны — закроются вместе с ботом)
    threading.Thread(target=reminder_loop, args=(bot,), daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    # Внешние копии памяти/кода в приватный Telegram-канал (Этап 1).
    # Запускается дополнительно к существующим процессам, не заменяя их.
    threading.Thread(target=backup_offsite_loop, args=(bot,), daemon=True).start()
    # Проактивность: Сенсей пишет первым (Этап 6).
    threading.Thread(target=proactive_loop, args=(bot,), daemon=True).start()

    # 5. Старт
    print("AI OS STARTED")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
