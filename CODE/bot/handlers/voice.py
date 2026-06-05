"""
voice.py — Обработка голосовых сообщений
==========================================

ПРОСТЫМИ СЛОВАМИ:
Когда приходит голосовое сообщение, бот:
  1. Скачивает аудио.
  2. Конвертирует его в формат WAV.
  3. Распознаёт речь в текст (модель Whisper).
  4. Отправляет текст в AI и получает ответ.
  5. Сохраняет распознанный текст в документ Word и присылает его.
  6. Отвечает пользователю текстом голоса и ответом AI.
"""

from pydub import AudioSegment

from bot import config
from bot.services.ai import ask_ai, client
from bot.utils.docx import save_voice_transcript


def register(bot) -> None:
    """Регистрирует обработчик голосовых сообщений."""

    @bot.message_handler(content_types=['voice'])
    def handle_voice(message):
        try:
            user_id = message.chat.id

            file_info = bot.get_file(message.voice.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            ogg_path = str(config.VOICE_DIR / f"{user_id}.ogg")
            wav_path = str(config.VOICE_DIR / f"{user_id}.wav")

            with open(ogg_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            audio = AudioSegment.from_file(ogg_path)
            audio.export(wav_path, format="wav")

            with open(wav_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )

            text = transcript.text

            ai_text = ask_ai(user_id, text)

            transcript_path = save_voice_transcript(user_id, text)

            with open(transcript_path, "rb") as f:
                bot.send_document(message.chat.id, f)

            bot.reply_to(
                message,
                f"🎤 Твой голос:\n\n{text}\n\n🤖 Ответ:\n\n{ai_text}",
            )

        except Exception as e:
            bot.reply_to(message, f"Voice error:\n{e}")
