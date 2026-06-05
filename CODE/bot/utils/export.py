"""
export.py — Текстовый (Markdown) экспорт памяти
=================================================

ПРОСТЫМИ СЛОВАМИ:
Этот файл собирает из базы данных человекочитаемый документ:
историю диалогов + задачи + напоминания. Такой файл можно дать ЛЮБОМУ ИИ,
и он «узнает» пользователя, даже без самого файла базы данных.

Важно: экспорт строится ТОЛЬКО из фактически доступных таблиц.
Если какой-то таблицы нет — раздел помечается как отсутствующий,
а экспорт не падает (forward-compatible с будущим профилем, Этап 7).
"""

import sqlite3
from datetime import datetime, timezone

from bot import config


def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def build_memory_export() -> str:
    """
    Читает базу и возвращает текст экспорта в формате Markdown.

    Бросает исключение ТОЛЬКО при ошибке открытия/чтения базы — вызывающий код
    (telegram_backup) перехватит её, залогирует и пропустит отправку экспорта
    целиком в этом цикле (без отправки частичных данных).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines: list[str] = []
    lines.append("# SENSEI — Экспорт памяти")
    lines.append("")
    lines.append(f"_Сформировано: {now}_")
    lines.append("")
    lines.append(
        "Это человекочитаемая копия памяти бота Sensei. "
        "Её можно дать любому ИИ, чтобы он понял контекст пользователя."
    )
    lines.append("")

    # Открываем отдельное подключение только для чтения (не трогаем общее).
    conn = sqlite3.connect(str(config.DB_PATH))
    try:
        cur = conn.cursor()

        # --- История диалогов (таблица memory) ---
        lines.append("## История диалогов")
        lines.append("")
        if _table_exists(cur, "memory"):
            cur.execute(
                "SELECT user_id, role, content, created_at FROM memory ORDER BY id ASC"
            )
            rows = cur.fetchall()
            if rows:
                for user_id, role, content, created_at in rows:
                    role_label = "🧑 Пользователь" if role == "user" else "🤖 Sensei"
                    ts = created_at or ""
                    lines.append(f"**{role_label}** ({ts}):")
                    lines.append("")
                    lines.append((content or "").strip())
                    lines.append("")
            else:
                lines.append("_История пуста._")
                lines.append("")
        else:
            lines.append("_Таблица `memory` отсутствует — раздел пропущен._")
            lines.append("")

        # --- Задачи (таблица tasks) ---
        lines.append("## Задачи")
        lines.append("")
        if _table_exists(cur, "tasks"):
            cur.execute(
                "SELECT id, user_id, task, status, created_at FROM tasks ORDER BY id ASC"
            )
            rows = cur.fetchall()
            if rows:
                for task_id, user_id, task, status, created_at in rows:
                    status_label = status or "—"
                    lines.append(f"- [{status_label}] #{task_id}: {(task or '').strip()}")
                lines.append("")
            else:
                lines.append("_Задач нет._")
                lines.append("")
        else:
            lines.append("_Таблица `tasks` отсутствует — раздел пропущен._")
            lines.append("")

        # --- Напоминания (таблица reminders) ---
        lines.append("## Напоминания")
        lines.append("")
        if _table_exists(cur, "reminders"):
            cur.execute(
                "SELECT id, user_id, reminder, remind_time, sent FROM reminders ORDER BY id ASC"
            )
            rows = cur.fetchall()
            if rows:
                for rem_id, user_id, reminder, remind_time, sent in rows:
                    sent_label = "отправлено" if sent else "ожидает"
                    lines.append(
                        f"- #{rem_id} [{sent_label}] на {remind_time}: "
                        f"{(reminder or '').strip()}"
                    )
                lines.append("")
            else:
                lines.append("_Напоминаний нет._")
                lines.append("")
        else:
            lines.append("_Таблица `reminders` отсутствует — раздел пропущен._")
            lines.append("")

        return "\n".join(lines)
    finally:
        conn.close()
