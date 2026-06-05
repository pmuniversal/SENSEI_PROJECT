"""
commands.py — Команды бота (/task, /tasks, /remind)
====================================================

ПРОСТЫМИ СЛОВАМИ:
Здесь обрабатываются команды, которые начинаются со слэша:
  /task <текст>                  — добавить задачу
  /tasks                         — показать список задач
  /remind <время> | <текст>      — поставить напоминание

ВАЖНО (исправление бага):
В старой версии команда /tasks ошибочно срабатывала как /task
(потому что слово "/tasks" начинается с "/task"), и вместо списка
создавалась задача с текстом "s". Теперь команды распознаются ТОЧНО,
поэтому /task и /tasks работают правильно и независимо.
"""

from bot.services.tasks import add_task, list_tasks
from bot.services.reminders import add_reminder
from bot.services.telegram_backup import run_on_demand_backup


def register(bot) -> None:
    """Регистрирует все командные обработчики в боте."""

    @bot.message_handler(commands=['backup'])
    def cmd_backup(message):
        # Копия по запросу: немедленно шлёт базу + экспорт в приватный канал.
        try:
            run_on_demand_backup(bot, message.chat.id)
        except Exception as e:
            bot.reply_to(message, f"Ошибка при создании копии:\n{e}")

    @bot.message_handler(commands=['task'])
    def cmd_task(message):
        try:
            # Берём текст после "/task". Если текста нет — пустая строка.
            parts = message.text.split(maxsplit=1)
            task_text = parts[1].strip() if len(parts) > 1 else ""

            add_task(message.chat.id, task_text)

            bot.reply_to(
                message,
                f"✅ Задача добавлена:\n\n{task_text}",
            )
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    @bot.message_handler(commands=['tasks'])
    def cmd_tasks(message):
        try:
            rows = list_tasks(message.chat.id)

            if not rows:
                bot.reply_to(message, "Нет активных задач")
                return

            result = "📌 ТВОИ ЗАДАЧИ:\n\n"
            for row in rows:
                result += f"{row[0]}. {row[1]}\n"

            bot.reply_to(message, result)
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    @bot.message_handler(commands=['remind'])
    def cmd_remind(message):
        try:
            # Текст после "/remind", ожидаем формат: "время | текст"
            parts = message.text.split(maxsplit=1)
            data = parts[1].strip() if len(parts) > 1 else ""

            split_data = data.split("|")
            remind_time = split_data[0].strip()
            reminder_text = split_data[1].strip()

            add_reminder(message.chat.id, remind_time, reminder_text)

            bot.reply_to(
                message,
                f"⏰ Напоминание сохранено:\n\n{reminder_text}",
            )
        except Exception:
            bot.reply_to(
                message,
                "Формат:\n/remind 2026-05-25 18:00 | Текст",
            )
