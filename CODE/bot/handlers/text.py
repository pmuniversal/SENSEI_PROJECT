"""
text.py — Обработка обычных текстовых сообщений
================================================

ПРОСТЫМИ СЛОВАМИ:
Если пользователь написал обычный текст (НЕ команду со слэшем),
бот отправляет его в AI и отвечает.

Фильтр "не начинается со слэша" гарантирует, что команды (/task, /tasks,
/remind) обрабатываются только в commands.py и не попадают сюда дважды.
"""

from bot.services.ai import ask_ai
from bot.services.telegram_backup import run_on_demand_backup

# Фразы на естественном языке, которые запускают копию по запросу
_BACKUP_PHRASES = {
    "сделай копию сейчас",
    "сделай копию",
    "сделай бэкап",
    "сделай бэкап сейчас",
}


def register(bot) -> None:
    """Регистрирует обработчик обычных текстовых сообщений."""

    @bot.message_handler(
        func=lambda m: m.content_type == 'text' and not m.text.startswith('/')
    )
    def handle_text(message):
        try:
            normalized = message.text.strip().lower().rstrip("!.")

            # Резервная копия по фразе
            if normalized in _BACKUP_PHRASES:
                run_on_demand_backup(bot, message.chat.id)
                return

            # Проверяем: ожидает ли голосовой обработчик контекст от этого юзера
            from bot.handlers.voice import _pending_context, _pending_audio
            user_id = message.chat.id
            if user_id in _pending_context and _pending_context[user_id] == "waiting_context":
                from bot.services.voice_processor import detect_mode
                from bot.handlers.voice import _process_voice_file

                context_text = message.text.strip()
                if user_id in _pending_audio:
                    audio_data = _pending_audio.pop(user_id)
                    del _pending_context[user_id]
                    mode = detect_mode(context_text)
                    _process_voice_file(bot, message, user_id, audio_data["ogg_path"], mode, context_text)
                    return
                else:
                    del _pending_context[user_id]

            # Финансовый ввод (приоритет выше умного ввода — более детальный парсер)
            from bot.services.finance import process_finance
            finance_result = process_finance(message.chat.id, message.text)
            if finance_result is not None:
                bot.reply_to(message, finance_result, parse_mode="Markdown")
                return

            # Умный ввод: задача, напоминание, запрос задач
            from bot.services.smart_input import process_smart_input
            smart_result = process_smart_input(message.chat.id, message.text, bot, message)
            if smart_result is not None:
                bot.reply_to(message, smart_result)
                return

            ai_text = ask_ai(message.chat.id, message.text)
            bot.reply_to(message, ai_text)
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")
