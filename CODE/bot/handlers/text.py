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

# Максимальная длина одного сообщения Telegram
_MAX_MSG_LEN = 4000


def _send_long(bot, message, text: str, parse_mode: str = None):
    """Отправляет длинный текст разбивая на части по 4000 символов."""
    if len(text) <= _MAX_MSG_LEN:
        if parse_mode:
            bot.reply_to(message, text, parse_mode=parse_mode)
        else:
            bot.reply_to(message, text)
        return

    # Разбиваем по абзацам, чтобы не резать на середине предложения
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > _MAX_MSG_LEN:
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current.strip())

    # Первый чанк — reply, остальные — отдельными сообщениями
    for i, chunk in enumerate(chunks):
        try:
            if i == 0:
                if parse_mode:
                    bot.reply_to(message, chunk, parse_mode=parse_mode)
                else:
                    bot.reply_to(message, chunk)
            else:
                if parse_mode:
                    bot.send_message(message.chat.id, chunk, parse_mode=parse_mode)
                else:
                    bot.send_message(message.chat.id, chunk)
        except Exception:
            # Если Markdown сломан в чанке — отправляем без форматирования
            try:
                if i == 0:
                    bot.reply_to(message, chunk)
                else:
                    bot.send_message(message.chat.id, chunk)
            except Exception:
                pass


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
                _send_long(bot, message, finance_result, parse_mode="Markdown")
                return

            # Трекеры: привычки, сон, вес, дофамин
            from bot.services.trackers import process_tracker
            tracker_result = process_tracker(message.chat.id, message.text)
            if tracker_result is not None:
                _send_long(bot, message, tracker_result, parse_mode="Markdown")
                return

            # Умный ввод: задача, напоминание, запрос задач
            from bot.services.smart_input import process_smart_input
            smart_result = process_smart_input(message.chat.id, message.text, bot, message)
            if smart_result is not None:
                _send_long(bot, message, smart_result)
                return

            ai_text = ask_ai(message.chat.id, message.text)
            _send_long(bot, message, ai_text)
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")
