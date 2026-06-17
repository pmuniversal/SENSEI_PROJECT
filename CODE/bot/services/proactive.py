"""
proactive.py — Проактивность: Сенсей пишет первым (Этап 6)
============================================================

Сенсей сам инициирует сообщения — не ждёт пока напишут:
  - 🌅 Утренний брифинг (09:00): задачи на день по сферам, напоминания
  - 🌙 Вечерний разбор (21:00): что сделано, что перенести, вопрос о прогрессе
  - 🎯 Фокус-напоминание (через день в 14:00): прогресс по целям
  - ⏰ Дедлайны: напоминает за день до дедлайна задачи

Принципы:
  - НЕ спамит: максимум 3 сообщения в день
  - Учитывает профиль и задачи владельца
  - Жёсткий но без давления — направляет, а не раздражает
"""

import time
import threading
from datetime import datetime, date, timedelta

from bot.services.ai import client
from bot.services.tasks import list_tasks
from bot.services.reminders import add_reminder
from bot.database import db
from bot import config


# ──────────────────────────────────────────────────
# Состояние — чтобы не дублировать сообщения
# ──────────────────────────────────────────────────
_sent_today: dict = {}  # {user_id: set(message_types)}


def _already_sent(user_id, msg_type: str) -> bool:
    today = date.today().isoformat()
    key = f"{user_id}:{today}"
    if key not in _sent_today:
        _sent_today[key] = set()
    return msg_type in _sent_today[key]


def _mark_sent(user_id, msg_type: str):
    today = date.today().isoformat()
    key = f"{user_id}:{today}"
    if key not in _sent_today:
        _sent_today[key] = set()
    _sent_today[key].add(msg_type)


# ──────────────────────────────────────────────────
# Получить владельца
# ──────────────────────────────────────────────────
def _get_owner_id() -> str | None:
    """Возвращает OWNER_CHAT_ID из config или из БД (самый активный пользователь)."""
    import os
    owner = os.environ.get("OWNER_CHAT_ID", "").strip()
    if owner:
        return owner

    # Fallback: берём user_id с наибольшим количеством сообщений
    try:
        db.cursor.execute(
            "SELECT user_id, COUNT(*) as cnt FROM memory GROUP BY user_id ORDER BY cnt DESC LIMIT 1"
        )
        row = db.cursor.fetchone()
        if row:
            return str(row[0])
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────
# Генерация сообщений через GPT
# ──────────────────────────────────────────────────
def _generate_morning_brief(tasks: list, reminders_today: list) -> str:
    """Генерирует утренний брифинг."""
    task_text = "\n".join([f"• {t[1]}" for t in tasks[:10]]) if tasks else "Нет активных задач"
    remind_text = "\n".join([f"• {r[2]} в {r[3]}" for r in reminders_today]) if reminders_today else "Нет"

    today_str = datetime.now().strftime("%d %B %Y, %A")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — Сенсей, жёсткий наставник Бекзода. "
                    "Пишешь утренний брифинг. Коротко, конкретно, мотивирующе. "
                    "Максимум 150 слов. Без воды. Напомни про цель $30k и 4 сферы если уместно."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Дата: {today_str}\n"
                    f"Активные задачи:\n{task_text}\n"
                    f"Напоминания на сегодня:\n{remind_text}"
                )
            }
        ],
        max_tokens=250,
        temperature=0.7,
    )
    return response.choices[0].message.content


def _generate_evening_review(tasks: list) -> str:
    """Генерирует вечерний разбор."""
    task_text = "\n".join([f"• {t[1]}" for t in tasks[:8]]) if tasks else "Нет задач"

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — Сенсей, жёсткий наставник Бекзода. "
                    "Пишешь вечерний разбор дня. Коротко, честно. "
                    "Задай 1-2 вопроса о прогрессе. Максимум 120 слов."
                )
            },
            {
                "role": "user",
                "content": f"Текущие задачи:\n{task_text}"
            }
        ],
        max_tokens=200,
        temperature=0.7,
    )
    return response.choices[0].message.content


def _generate_focus_reminder() -> str:
    """Генерирует напоминание о фокусе на целях."""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — Сенсей, жёсткий наставник Бекзода. "
                    "Пишешь короткое (50-80 слов) напоминание о фокусе. "
                    "Напомни о главной цели ($30k), удержи от распыления. "
                    "Задай один конкретный вопрос о прогрессе за последние 2 дня."
                )
            },
            {"role": "user", "content": "Напиши напоминание о фокусе"}
        ],
        max_tokens=150,
        temperature=0.8,
    )
    return response.choices[0].message.content


# ──────────────────────────────────────────────────
# Получить напоминания на сегодня
# ──────────────────────────────────────────────────
def _get_todays_reminders(user_id: str) -> list:
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    try:
        db.cursor.execute(
            "SELECT id, user_id, reminder, remind_time FROM reminders "
            "WHERE user_id=? AND remind_time >= ? AND remind_time < ? AND sent=0",
            (str(user_id), today, tomorrow)
        )
        return db.cursor.fetchall()
    except Exception:
        return []


def _get_deadline_tasks(user_id: str) -> list:
    """Задачи с дедлайном завтра."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    try:
        rows = list_tasks(user_id)
        return [r for r in rows if tomorrow in str(r[1])]
    except Exception:
        return []


# ──────────────────────────────────────────────────
# Отправка проактивных сообщений
# ──────────────────────────────────────────────────
def send_morning_brief(bot, user_id: str):
    """Утренний брифинг."""
    if _already_sent(user_id, "morning"):
        return
    try:
        tasks = list_tasks(user_id)
        reminders = _get_todays_reminders(user_id)
        text = f"🌅 *Доброе утро, Бекзод!*\n\n{_generate_morning_brief(tasks, reminders)}"
        bot.send_message(user_id, text, parse_mode="Markdown")
        _mark_sent(user_id, "morning")
    except Exception as e:
        print(f"[PROACTIVE] Ошибка утреннего брифинга: {e}")


def send_evening_review(bot, user_id: str):
    """Вечерний разбор."""
    if _already_sent(user_id, "evening"):
        return
    try:
        tasks = list_tasks(user_id)
        text = f"🌙 *Вечерний разбор*\n\n{_generate_evening_review(tasks)}"
        
        # Добавляем вопрос про трекеры
        text += "\n\n📊 *Трекеры на сегодня:*\nСколько спал? Залипал в телефон? Вес? Отметь привычки."
        
        bot.send_message(user_id, text, parse_mode="Markdown")
        _mark_sent(user_id, "evening")
    except Exception as e:
        print(f"[PROACTIVE] Ошибка вечернего разбора: {e}")


def send_focus_reminder(bot, user_id: str):
    """Напоминание о фокусе (через день)."""
    if _already_sent(user_id, "focus"):
        return
    try:
        text = f"🎯 *Фокус*\n\n{_generate_focus_reminder()}"
        bot.send_message(user_id, text, parse_mode="Markdown")
        _mark_sent(user_id, "focus")
    except Exception as e:
        print(f"[PROACTIVE] Ошибка фокус-напоминания: {e}")


def send_deadline_alert(bot, user_id: str):
    """Предупреждение о дедлайне завтра."""
    if _already_sent(user_id, "deadline"):
        return
    try:
        tasks = _get_deadline_tasks(user_id)
        if not tasks:
            return
        lines = ["⏰ *Завтра дедлайн:*\n"]
        for t in tasks:
            lines.append(f"• {t[1]}")
        bot.send_message(user_id, "\n".join(lines), parse_mode="Markdown")
        _mark_sent(user_id, "deadline")
    except Exception as e:
        print(f"[PROACTIVE] Ошибка дедлайн-алерта: {e}")


def send_weekly_tracker_report(bot, user_id: str):
    """Еженедельный отчёт по трекерам (воскресенье)."""
    if _already_sent(user_id, "weekly_trackers"):
        return
    try:
        from bot.services.trackers import get_tracker_stats
        stats = get_tracker_stats(user_id, "all")
        if "Нет данных" in stats:
            return  # Не спамить если нет данных
        text = f"📈 *Еженедельный отчёт трекеров*\n\n{stats}"
        bot.send_message(user_id, text, parse_mode="Markdown")
        _mark_sent(user_id, "weekly_trackers")
    except Exception as e:
        print(f"[PROACTIVE] Ошибка еженедельного отчёта: {e}")


# ──────────────────────────────────────────────────
# Главный цикл
# ──────────────────────────────────────────────────
def proactive_loop(bot):
    """
    Фоновый поток. Проверяет время каждые 60 секунд.
    Отправляет сообщения по расписанию.
    """
    owner_id = _get_owner_id()
    if not owner_id:
        print("[PROACTIVE] OWNER_CHAT_ID не задан — добавь в .env. Проактивность отключена.")
        return

    print(f"[PROACTIVE] Запущен для user_id={owner_id}")

    # Счётчик для фокус-напоминания (через день)
    days_since_focus = [0]

    while True:
        try:
            now = datetime.now()
            hour = now.hour
            minute = now.minute

            # 09:00 — утренний брифинг
            if hour == 9 and minute == 0:
                send_morning_brief(bot, owner_id)

            # 21:00 — вечерний разбор
            elif hour == 21 and minute == 0:
                send_evening_review(bot, owner_id)
                days_since_focus[0] += 1

            # 14:00 через день — фокус-напоминание
            elif hour == 14 and minute == 0 and days_since_focus[0] % 2 == 0:
                send_focus_reminder(bot, owner_id)

            # 08:00 — дедлайн-алерт
            elif hour == 8 and minute == 0:
                send_deadline_alert(bot, owner_id)

            # Воскресенье 20:00 — еженедельный отчёт трекеров
            elif hour == 20 and minute == 0 and now.weekday() == 6:
                send_weekly_tracker_report(bot, owner_id)

        except Exception as e:
            print(f"[PROACTIVE] Ошибка в цикле: {e}")

        time.sleep(60)  # проверяем каждую минуту
