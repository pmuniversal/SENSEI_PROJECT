"""
voice.py — Умная обработка голосовых сообщений
===============================================

Логика:
  1. Получаем аудио (любая длина — от 10 сек до 60 мин)
  2. Проверяем есть ли контекст (предыдущее текстовое сообщение с режимом)
  3. Если контекста нет — спрашиваем у пользователя
  4. После получения режима — транскрибируем + обрабатываем:
     - 'meeting'  → Bayonnoma + Agenda (два Word файла)
     - 'summary'  → краткое резюме + ключевые мысли
     - 'finance'  → финансовая аналитика
     - 'chat'     → обычный диалог с AI

Режим можно указать ДО отправки аудио или В самом аудио.
"""

import os

from pydub import AudioSegment

from bot import config
from bot.services.ai import ask_ai
from bot.services.voice_processor import transcribe_audio, detect_mode
from bot.utils.docx import save_voice_transcript

# Словарь для хранения ожидаемых ответов: {user_id: 'waiting_voice_context'}
# и временного хранения аудио: {user_id: {'ogg_path': ..., 'wav_path': ...}}
_pending_context: dict = {}
_pending_audio: dict = {}


def _get_summary_prompt(transcript: str) -> str:
    return f"""Сделай профессиональное резюме аудиозаписи.

Структура ответа:
📌 Главная тема:
[1-2 предложения]

💡 Ключевые мысли:
• [мысль 1]
• [мысль 2]
• [...]

✅ Задачи / решения:
• [если есть]

🔑 Важные детали:
• [факты, цифры, имена]

Транскрипт:
{transcript}"""


def _get_finance_prompt(transcript: str) -> str:
    return f"""Это финансовая заметка или голосовой ввод финансовых данных.

Проанализируй и структурируй:
💰 Тип операции: (доход/расход/долг/другое)
📊 Сумма и категория:
📅 Дата/период:
💭 Комментарий:
📈 Рекомендация:

Если это вопрос — ответь как финансовый советник.

Данные:
{transcript}"""


def register(bot) -> None:
    """Регистрирует обработчики голосовых сообщений."""

    # Поддерживаемые аудио-расширения для обработки документов
    _AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".oga"}

    # --- Обработчик документов (аудио-файлы через скрепку) ---
    @bot.message_handler(content_types=["document"],
                         func=lambda m: m.document and any(
                             m.document.file_name.lower().endswith(ext) for ext in _AUDIO_EXTENSIONS
                         ) if m.document and m.document.file_name else False)
    def handle_audio_document(message):
        """Обрабатывает аудио-файлы отправленные как документы (m4a, mp3 и т.д.)"""
        user_id = message.chat.id
        try:
            bot.send_chat_action(message.chat.id, "typing")

            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)

            filename = message.document.file_name or "audio.m4a"
            ext = filename.split(".")[-1] if "." in filename else "m4a"
            audio_path = str(config.VOICE_DIR / f"{user_id}_doc.{ext}")

            with open(audio_path, "wb") as f:
                f.write(downloaded)

            # Определяем режим из caption
            mode = "unknown"
            context_hint = ""
            if message.caption:
                context_hint = message.caption
                mode = detect_mode(message.caption)

            if mode == "unknown":
                _pending_audio[user_id] = {"ogg_path": audio_path}
                _pending_context[user_id] = "waiting_context"
                bot.reply_to(
                    message,
                    f"🎤 Аудио-файл получил ({filename})! Скажи что с ним делать:\n\n"
                    "1️⃣ *Обычный разговор* — напиши «чат»\n"
                    "2️⃣ *Краткое резюме* — напиши «резюме»\n"
                    "3️⃣ *Протокол собрания* — напиши «собрание»\n"
                    "4️⃣ *Финансы* — напиши «финансы»\n\n"
                    "Или опиши своими словами.",
                    parse_mode="Markdown"
                )
                return

            _process_voice_file(bot, message, user_id, audio_path, mode, context_hint)

        except Exception as e:
            bot.reply_to(message, f"Ошибка обработки аудио-файла:\n{e}")

    # --- Основной обработчик голоса ---
    @bot.message_handler(content_types=["voice", "audio"])
    def handle_voice(message):
        user_id = message.chat.id

        try:
            bot.send_chat_action(message.chat.id, "typing")

            # Определяем file_id в зависимости от типа
            if message.voice:
                file_id = message.voice.file_id
            elif message.audio:
                file_id = message.audio.file_id
            else:
                bot.reply_to(message, "Не удалось определить аудио-файл.")
                return

            file_info = bot.get_file(file_id)
            downloaded = bot.download_file(file_info.file_path)

            # Определяем расширение из пути файла
            ext = file_info.file_path.split(".")[-1] if "." in file_info.file_path else "ogg"
            ogg_path = str(config.VOICE_DIR / f"{user_id}.{ext}")

            with open(ogg_path, "wb") as f:
                f.write(downloaded)

            # Определяем режим из caption или reply
            mode = "unknown"
            context_hint = ""

            # Если перед аудио было reply с текстом — используем его как контекст
            if message.reply_to_message and message.reply_to_message.text:
                context_hint = message.reply_to_message.text
                mode = detect_mode(context_hint)

            # Если в caption аудио указан режим
            if message.caption:
                context_hint = message.caption
                mode = detect_mode(message.caption)

            if mode == "unknown":
                # Сохраняем аудио и спрашиваем контекст
                _pending_audio[user_id] = {"ogg_path": ogg_path}
                _pending_context[user_id] = "waiting_context"

                bot.reply_to(
                    message,
                    "🎤 Аудио получил! Скажи что с ним делать:\n\n"
                    "1️⃣ *Обычный разговор* — напиши «чат» или «разговор»\n"
                    "2️⃣ *Краткое резюме* — напиши «резюме» или «краткое»\n"
                    "3️⃣ *Протокол собрания* (Bayonnoma + Agenda) — напиши «собрание» или «байоннома»\n"
                    "4️⃣ *Финансы* — напиши «финансы» или «деньги»\n\n"
                    "Или просто опиши своими словами что это за запись.",
                    parse_mode="Markdown"
                )
                return

            _process_voice_file(bot, message, user_id, ogg_path, mode, context_hint)

        except Exception as e:
            bot.reply_to(message, f"Ошибка обработки аудио:\n{e}")


def _process_voice_file(bot, message, user_id, ogg_path, mode, context_hint=""):
    """Транскрибирует аудио и обрабатывает по режиму."""
    try:
        # Запускаем транскрипцию с обратным отсчётом в одном сообщении
        status_msg = bot.reply_to(message, "⏳ Транскрибирую... 0 сек")

        # Таймер — обновляет сообщение каждые 5 сек пока идёт транскрипция
        import threading
        stop_timer = threading.Event()
        elapsed = [0]

        def _ticker():
            while not stop_timer.is_set():
                stop_timer.wait(5)
                if stop_timer.is_set():
                    break
                elapsed[0] += 5
                try:
                    bot.edit_message_text(
                        f"⏳ Транскрибирую... {elapsed[0]} сек",
                        message.chat.id,
                        status_msg.message_id
                    )
                except Exception:
                    pass

        ticker = threading.Thread(target=_ticker, daemon=True)
        ticker.start()

        try:
            transcript = transcribe_audio(ogg_path)
        finally:
            stop_timer.set()

        total_sec = elapsed[0] + 5
        try:
            bot.edit_message_text(
                f"✅ Готово за ~{total_sec} сек. Обрабатываю...",
                message.chat.id,
                status_msg.message_id
            )
        except Exception:
            pass

        if not transcript.strip():
            bot.edit_message_text(
                "⚠️ Не удалось распознать речь. Попробуй ещё раз.",
                message.chat.id, status_msg.message_id
            )
            return

        # Обработка по режиму
        if mode == "meeting":
            bot.edit_message_text(
                "📋 Транскрипция готова. Генерирую Bayonnoma и Agenda...",
                message.chat.id, status_msg.message_id
            )
            _handle_meeting(bot, message, user_id, transcript)

        elif mode == "summary":
            bot.edit_message_text(
                "📝 Составляю резюме...",
                message.chat.id, status_msg.message_id
            )
            _handle_summary(bot, message, user_id, transcript)

        elif mode == "finance":
            bot.edit_message_text(
                "💰 Анализирую финансовые данные...",
                message.chat.id, status_msg.message_id
            )
            _handle_finance(bot, message, user_id, transcript)

        else:
            bot.edit_message_text(
                "🤖 Передаю в AI...",
                message.chat.id, status_msg.message_id
            )
            _handle_chat(bot, message, user_id, transcript)

        # Удаляем статусное сообщение
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        bot.reply_to(message, f"Ошибка:\n{e}")
    finally:
        # Чистим временные файлы
        for ext in [".ogg", ".wav"]:
            p = ogg_path.replace(".ogg", ext)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


def _handle_meeting(bot, message, user_id, transcript):
    """Генерирует Bayonnoma + Agenda."""
    from bot.services.meeting import process_meeting_transcript

    bayonnoma_path, agenda_path, summary = process_meeting_transcript(transcript)

    # Отправляем резюме
    bot.reply_to(message, summary, parse_mode="Markdown")

    # Отправляем Bayonnoma
    with open(bayonnoma_path, "rb") as f:
        bot.send_document(
            message.chat.id, f,
            caption="📄 Bayonnoma (Протокол собрания)"
        )

    # Отправляем Agenda
    with open(agenda_path, "rb") as f:
        bot.send_document(
            message.chat.id, f,
            caption="📋 Agenda (Повестка следующего дня)"
        )

    # Сохраняем транскрипт
    transcript_path = save_voice_transcript(user_id, transcript)
    with open(transcript_path, "rb") as f:
        bot.send_document(message.chat.id, f, caption="🎤 Транскрипт")


def _handle_summary(bot, message, user_id, transcript):
    """Делает краткое резюме."""
    prompt = _get_summary_prompt(transcript)
    summary = ask_ai(user_id, prompt)
    bot.reply_to(message, f"📝 *Резюме:*\n\n{summary}", parse_mode="Markdown")

    transcript_path = save_voice_transcript(user_id, transcript)
    with open(transcript_path, "rb") as f:
        bot.send_document(message.chat.id, f, caption="🎤 Полный транскрипт")


def _handle_finance(bot, message, user_id, transcript):
    """Финансовая обработка — сохраняет в БД и выдаёт анализ."""
    from bot.services.finance import process_finance
    result = process_finance(user_id, transcript)
    if result:
        bot.reply_to(message, result, parse_mode="Markdown")
    else:
        prompt = f"Это финансовая заметка. Проанализируй и структурируй:\n\n{transcript}"
        analysis = ask_ai(user_id, prompt)
        bot.reply_to(message, f"💰 *Финансовый анализ:*\n\n{analysis}", parse_mode="Markdown")

    transcript_path = save_voice_transcript(user_id, transcript)
    with open(transcript_path, "rb") as f:
        bot.send_document(message.chat.id, f, caption="🎤 Транскрипт")


def _handle_chat(bot, message, user_id, transcript):
    """Обычный диалог с AI."""
    ai_response = ask_ai(user_id, transcript)

    bot.reply_to(
        message,
        f"🎤 *Твои слова:*\n{transcript}\n\n🤖 *Ответ:*\n{ai_response}",
        parse_mode="Markdown"
    )

    transcript_path = save_voice_transcript(user_id, transcript)
    with open(transcript_path, "rb") as f:
        bot.send_document(message.chat.id, f, caption="🎤 Транскрипт")
