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
# (дублируют команду /backup для удобства).
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
            # Распознаём фразу «сделай копию сейчас» как запрос резервной копии.
            normalized = message.text.strip().lower().rstrip("!.")
            if normalized in _BACKUP_PHRASES:
                run_on_demand_backup(bot, message.chat.id)
                return

            ai_text = ask_ai(message.chat.id, message.text)
            bot.reply_to(message, ai_text)
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")
