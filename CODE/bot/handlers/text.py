"""
text.py — Обработка обычных текстовых сообщений
================================================

ПРОСТЫМИ СЛОВАМИ:
Если пользователь написал обычный текст (НЕ команду со слэшем),
бот отправляет его в AI и отвечает.

Буферизация: если пользователь отправляет несколько сообщений подряд
быстро (в течении 2 секунд) — они склеиваются в одно и обрабатываются вместе.

Фильтр "не начинается со слэша" гарантирует, что команды (/task, /tasks,
/remind) обрабатываются только в commands.py и не попадают сюда дважды.
"""

import threading
import time

from bot.services.ai import ask_ai
from bot.services.telegram_backup import run_on_demand_backup

_MAX_MSG_LEN = 4000

# Фразы на естественном языке, которые запускают копию по запросу
_BACKUP_PHRASES = {
    "сделай копию сейчас",
    "сделай копию",
    "сделай бэкап",
    "сделай бэкап сейчас",
}

# Максимальная длина одного сообщения Telegram
_MAX_MSG_LEN = 4000

# Буфер сообщений: {user_id: {"texts": [...], "timer": Timer, "message": msg}}
_buffer: dict = {}
_buffer_lock = threading.Lock()
_BUFFER_DELAY = 2.0  # секунды ожидания перед обработкой


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

    def _process_buffered(user_id, bot_ref):
        """Обрабатывает накопленный буфер сообщений от пользователя."""
        with _buffer_lock:
            if user_id not in _buffer:
                return
            data = _buffer.pop(user_id)

        combined_text = "\n\n".join(data["texts"])
        message = data["message"]

        try:
            bot_ref.send_chat_action(message.chat.id, "typing")
            normalized = combined_text.strip().lower().rstrip("!.")
            text_lower = combined_text.lower()

            # Резервная копия по фразе
            if normalized in _BACKUP_PHRASES:
                run_on_demand_backup(bot_ref, message.chat.id)
                return

            # Голосовой контекст
            from bot.handlers.voice import _pending_context, _pending_audio
            if user_id in _pending_context and _pending_context[user_id] == "waiting_context":
                from bot.services.voice_processor import detect_mode
                from bot.handlers.voice import _process_voice_file
                if user_id in _pending_audio:
                    audio_data = _pending_audio.pop(user_id)
                    del _pending_context[user_id]
                    mode = detect_mode(combined_text)
                    _process_voice_file(bot_ref, message, user_id, audio_data["ogg_path"], mode, combined_text)
                    return
                else:
                    del _pending_context[user_id]

            # Единый умный классификатор → роутит в finance/tracker/task/reminder/knowledge/chat
            from bot.services.smart_input import process_smart_input
            smart_result = process_smart_input(user_id, combined_text, bot_ref, message)
            if smart_result is not None:
                _send_long(bot_ref, message, smart_result, parse_mode="Markdown")
                return

            # AI (обычный разговор)
            ai_text = ask_ai(user_id, combined_text)
            if not ai_text or not ai_text.strip():
                ai_text = "Получил. Напиши ещё раз если нет ответа."
            _send_long(bot_ref, message, ai_text)

        except Exception as e:
            try:
                bot_ref.reply_to(message, f"Ошибка:\n{e}")
            except Exception:
                pass

    @bot.message_handler(
        func=lambda m: m.content_type == 'text' and not m.text.startswith('/')
    )
    def handle_text(message):
        user_id = message.chat.id
        text = message.text.strip()

        with _buffer_lock:
            if user_id in _buffer:
                # Отменяем старый таймер и добавляем текст в буфер
                _buffer[user_id]["timer"].cancel()
                _buffer[user_id]["texts"].append(text)
                # Обновляем message на последнее (для reply_to)
                _buffer[user_id]["message"] = message
            else:
                _buffer[user_id] = {
                    "texts": [text],
                    "message": message,
                    "timer": None,
                }

            # Запускаем новый таймер
            timer = threading.Timer(_BUFFER_DELAY, _process_buffered, args=(user_id, bot))
            _buffer[user_id]["timer"] = timer
            timer.start()
