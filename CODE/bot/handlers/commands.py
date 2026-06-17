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
from bot.services.reminders import add_reminder, list_reminders, delete_reminder
from bot.services.roles import set_role, get_role, get_role_name, AVAILABLE_ROLES
from bot.services.telegram_backup import run_on_demand_backup


def register(bot) -> None:
    """Регистрирует все командные обработчики в боте."""

    @bot.message_handler(commands=['role', 'mode'])
    def cmd_role(message):
        """Выбрать или показать текущую роль."""
        try:
            parts = message.text.split(maxsplit=1)
            user_id = message.chat.id
            if len(parts) == 1:
                # Показать текущую роль и список доступных
                current = get_role(user_id)
                lines = [f"🎭 Текущая роль: *{get_role_name(current)}*\n"]
                lines.append("Доступные роли:")
                role_map = {
                    "coach": "🧠 /role coach — ICF-коуч",
                    "analyst": "📊 /role analyst — Бизнес-аналитик",
                    "finance": "💰 /role finance — Финансист",
                    "youtube": "🎥 /role youtube — YouTube-эксперт",
                    "services": "🌐 /role services — Услуги США/AU/CA",
                    "meeting": "📋 /role meeting — Модератор встреч",
                    "tech": "💻 /role tech — Технический советник",
                    "sensei": "🔮 /role sensei — Базовый Сенсей",
                    "auto": "🔄 /role auto — Авто (определяет сам)",
                }
                for v in role_map.values():
                    lines.append(v)
                bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")
                return

            role_input = parts[1].strip().lower()
            if role_input == "auto":
                set_role(user_id, "sensei", locked=False)
                bot.reply_to(message, "🔄 Авто-режим: роль определяется по контексту сообщения.")
                return
            if role_input not in AVAILABLE_ROLES:
                bot.reply_to(message, f"Неизвестная роль. Напиши /role чтобы увидеть список.")
                return
            set_role(user_id, role_input, locked=True)
            bot.reply_to(message, f"✅ Роль установлена: *{get_role_name(role_input)}*\n\nЧтобы вернуть авто-режим: /role auto", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    @bot.message_handler(commands=['backup'])
    def cmd_backup(message):
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
            parts = message.text.split(maxsplit=1)
            data = parts[1].strip() if len(parts) > 1 else ""
            split_data = data.split("|")
            remind_time = split_data[0].strip()
            reminder_text = split_data[1].strip()
            normalized = add_reminder(message.chat.id, remind_time, reminder_text)
            bot.reply_to(message, f"⏰ Напоминание сохранено:\n\n{reminder_text}\n📅 Когда: {normalized}")
        except Exception:
            bot.reply_to(message, "Формат:\n/remind 2026-06-17 09:00 | Текст")

    @bot.message_handler(commands=['reminders'])
    def cmd_reminders(message):
        """Показать список активных напоминаний."""
        try:
            rows = list_reminders(message.chat.id)
            if not rows:
                bot.reply_to(message, "⏰ Нет активных напоминаний.")
                return
            lines = ["⏰ *Активные напоминания:*\n"]
            for rid, text, rtime in rows:
                lines.append(f"`{rid}.` {rtime}\n   ➜ {text}")
            lines.append("\nЧтобы удалить: /delreminder [id]")
            bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    @bot.message_handler(commands=['delreminder'])
    def cmd_delreminder(message):
        """Удалить напоминание по ID."""
        try:
            parts = message.text.split(maxsplit=1)
            rid = int(parts[1].strip()) if len(parts) > 1 else None
            if rid is None:
                bot.reply_to(message, "Формат: /delreminder [id]\nID смотри в /reminders")
                return
            if delete_reminder(rid, message.chat.id):
                bot.reply_to(message, f"✅ Напоминание #{rid} удалено.")
            else:
                bot.reply_to(message, f"❌ Напоминание #{rid} не найдено.")
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    # ──────────────────────────────────────────────────
    # База знаний (Этап 15)
    # ──────────────────────────────────────────────────
    @bot.message_handler(commands=['learn'])
    def cmd_learn(message):
        """Загрузить YouTube видео в базу знаний."""
        try:
            from bot.services.knowledge import ingest_youtube
            parts = message.text.split(maxsplit=1)
            url = parts[1].strip() if len(parts) > 1 else ""
            if not url or "youtu" not in url:
                bot.reply_to(message, "Формат: /learn <YouTube URL>\n\nПример:\n/learn https://www.youtube.com/watch?v=xxxxx")
                return
            bot.send_chat_action(message.chat.id, "typing")
            bot.reply_to(message, "📥 Загружаю и анализирую видео... Это может занять 30-60 сек.")
            result = ingest_youtube(message.chat.id, url)
            bot.send_message(message.chat.id, result, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    @bot.message_handler(commands=['knowledge'])
    def cmd_knowledge(message):
        """Показать базу знаний."""
        try:
            from bot.services.knowledge import list_knowledge
            result = list_knowledge(message.chat.id)
            bot.reply_to(message, result, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")

    @bot.message_handler(commands=['search'])
    def cmd_search(message):
        """Поиск по базе знаний."""
        try:
            from bot.services.knowledge import search_knowledge
            parts = message.text.split(maxsplit=1)
            query = parts[1].strip() if len(parts) > 1 else ""
            if not query:
                bot.reply_to(message, "Формат: /search <запрос>\n\nПример:\n/search YouTube алгоритм")
                return
            result = search_knowledge(message.chat.id, query)
            bot.reply_to(message, result, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Ошибка:\n{e}")
