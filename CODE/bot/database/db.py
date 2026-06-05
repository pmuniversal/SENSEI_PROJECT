"""
db.py — Слой базы данных (SQLite)
==================================

ПРОСТЫМИ СЛОВАМИ:
Здесь живёт подключение к базе данных и создание таблиц.
База данных — это файл memory.db, в котором хранятся:
  - memory    : история диалогов (память бота)
  - tasks     : задачи
  - reminders : напоминания

Структура таблиц полностью совпадает со старой версией —
никакие данные не теряются.
"""

import sqlite3

from bot import config


def get_connection() -> sqlite3.Connection:
    """
    Открывает подключение к базе данных.

    Сначала убеждается, что папка для данных существует
    (SQLite сам папки не создаёт). Затем подключается к файлу memory.db.

    check_same_thread=False нужно, чтобы фоновые процессы
    (напоминания и бэкапы) могли пользоваться базой.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(config.DB_PATH), check_same_thread=False)


def init_db(connection: sqlite3.Connection) -> None:
    """
    Создаёт таблицы, если их ещё нет.
    'CREATE TABLE IF NOT EXISTS' = создать только если таблицы нет,
    поэтому существующие данные не затрагиваются.
    """
    db_cursor = connection.cursor()

    db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        role TEXT,
        content TEXT,
        created_at TEXT
    )
    """)

    db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        task TEXT,
        status TEXT,
        created_at TEXT
    )
    """)

    db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        reminder TEXT,
        remind_time TEXT,
        sent INTEGER DEFAULT 0
    )
    """)

    connection.commit()


# --------------------------------------------------
# Общие объекты на весь проект
# --------------------------------------------------
# conn и cursor создаются один раз и используются всеми модулями
# (так же, как было в старом main.py).
conn: sqlite3.Connection = get_connection()
cursor: sqlite3.Cursor = conn.cursor()

init_db(conn)
