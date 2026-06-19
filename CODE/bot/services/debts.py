"""
debts.py — Единый источник правды по долгам и кредитам
========================================================

ПРОСТЫМИ СЛОВАМИ:
Раньше все долги были "вшиты" в код в трёх местах (промпт AI, finance.py, Google Sheets)
и бот не мог их менять. Теперь все долги хранятся в базе данных (таблица debts),
и бот умеет:
  - показывать актуальную сводку (читает из БД)
  - менять сумму долга голосом/текстом ("измени долг Pulinform на 25 млн")
  - уменьшать долг при погашении ("отдал $100 Сирожу")

Категории (category):
  - 'bank'           — банковские кредиты (в сумах)
  - 'person_i_owe'   — люди, которым должен Я (в долларах)
  - 'person_owes_me' — люди, которые должны МНЕ (в долларах)
"""

from datetime import datetime

from bot.database import db


# ──────────────────────────────────────────────────
# Инициализация таблицы
# ──────────────────────────────────────────────────
def init_debts_table():
    db.cursor.execute("""
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,        -- 'bank' | 'person_i_owe' | 'person_owes_me'
        name TEXT,            -- название (Анорбанк №1, Сирож ака, ...)
        amount REAL,          -- сумма долга
        currency TEXT,        -- 'UZS' | 'USD'
        rate TEXT,            -- ставка (для банков), напр. '42%'
        note TEXT,            -- метка: просрочка / срочно / дата / критично
        sort_order INTEGER,   -- порядок вывода
        updated_at TEXT
    )
    """)
    db.conn.commit()


# ──────────────────────────────────────────────────
# Первичное наполнение (один раз, если таблица пуста)
# ──────────────────────────────────────────────────
_SEED = [
    # category, name, amount, currency, rate, note, sort_order
    ("bank", "Анорбанк №1",         17545179, "UZS", "42%",  "",                      1),
    ("bank", "Анорбанк №2",         16240921, "UZS", "47%",  "⚠️ просрочка",          2),
    ("bank", "AVO карта",           23510000, "UZS", "45%+", "",                      3),
    ("bank", "Узумбанк",            22000000, "UZS", "44%",  "⚠️ просрочка",          4),
    ("bank", "Юрлица (гос.)",       95000000, "UZS", "23%",  "🔴 КРИТИЧНО до 30.06",  5),
    ("bank", "Pulinform рассрочка", 25000000, "UZS", "0%",   "",                      6),

    ("person_i_owe", "Сирож ака", 600,  "USD", "", "(до 10.07.2026) 🔴 СРОЧНО", 1),
    ("person_i_owe", "Навруз",    1600, "USD", "", "⚠️ срочный",                2),
    ("person_i_owe", "Истам",     2287, "USD", "", "⚠️ приоритет",              3),
    ("person_i_owe", "Иван",      4920, "USD", "", "(не срочный)",              4),
    ("person_i_owe", "Илёс ака",  100,  "USD", "", "",                          5),

    ("person_owes_me", "Навруз",       1600, "USD", "", "", 1),
    ("person_owes_me", "Умар",         200,  "USD", "", "", 2),
    ("person_owes_me", "Лазиз (брат)", 300,  "USD", "", "", 3),
]


def seed_debts_if_empty():
    """Наполняет таблицу начальными данными, только если она пустая."""
    db.cursor.execute("SELECT COUNT(*) FROM debts")
    count = db.cursor.fetchone()[0]
    if count > 0:
        return
    now = str(datetime.now())
    for cat, name, amount, curr, rate, note, order in _SEED:
        db.cursor.execute("""
        INSERT INTO debts (category, name, amount, currency, rate, note, sort_order, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cat, name, amount, curr, rate, note, order, now))
    db.conn.commit()
    print("[DEBTS] Таблица долгов наполнена начальными данными")


init_debts_table()
seed_debts_if_empty()


# ──────────────────────────────────────────────────
# Чтение
# ──────────────────────────────────────────────────
def _fmt_uzs(amount: float) -> str:
    return f"{amount:,.0f} сум".replace(",", " ")


def _fmt_usd(amount: float) -> str:
    return f"${amount:,.0f}".replace(",", " ")


def get_all_debts(category: str = None) -> list:
    """Возвращает все долги (или одной категории) в порядке sort_order."""
    if category:
        db.cursor.execute(
            "SELECT category, name, amount, currency, rate, note FROM debts WHERE category=? ORDER BY sort_order",
            (category,)
        )
    else:
        db.cursor.execute(
            "SELECT category, name, amount, currency, rate, note FROM debts ORDER BY category, sort_order"
        )
    return db.cursor.fetchall()


def get_debts_summary_text() -> str:
    """Формирует читаемую сводку долгов ИЗ БАЗЫ ДАННЫХ."""
    lines = []

    # ── Кому ТЫ должен ──────────────────────────────
    lines.append("💳 *Кому я должен:*\n")
    lines.append("🏦 Банки:")
    for _, name, amount, curr, rate, note in get_all_debts("bank"):
        rate_str = f" ({rate})" if rate else ""
        note_str = f" {note}" if note else ""
        lines.append(f"  • {name} — *{_fmt_uzs(amount)}*{rate_str}{note_str}")

    lines.append("")
    lines.append("👥 Люди (я должен им):")
    total_i_owe = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("person_i_owe"):
        note_str = f" {note}" if note else ""
        lines.append(f"  • {name} — *{_fmt_usd(amount)}*{note_str}")
        total_i_owe += amount
    lines.append("")
    lines.append(f"📊 Итого личных долгов: *{_fmt_usd(total_i_owe)}*")

    # ── Кто должен ТЕБЕ ─────────────────────────────
    lines.append("")
    lines.append("💰 *Кто должен мне:*\n")
    total_owed = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("person_owes_me"):
        lines.append(f"  • {name} — *{_fmt_usd(amount)}*")
        total_owed += amount
    lines.append("")
    lines.append(f"📊 Итого должны мне: *{_fmt_usd(total_owed)}*")

    return "\n".join(lines)


def get_debts_for_prompt() -> str:
    """Компактная сводка долгов для подстановки в системный промпт AI.

    Так AI ВСЕГДА видит актуальные цифры из БД, а не устаревший хардкод.
    """
    parts = ["ТЕКУЩИЕ ДОЛГИ (актуально из базы, всегда опирайся на эти цифры):"]

    parts.append("Банковские кредиты:")
    for _, name, amount, curr, rate, note in get_all_debts("bank"):
        rate_str = f", {rate}" if rate else ""
        note_str = f" [{note}]" if note else ""
        parts.append(f"  - {name}: {_fmt_uzs(amount)}{rate_str}{note_str}")

    parts.append("Личные долги (должен людям):")
    total_i_owe = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("person_i_owe"):
        note_str = f" [{note}]" if note else ""
        parts.append(f"  - {name}: {_fmt_usd(amount)}{note_str}")
        total_i_owe += amount
    parts.append(f"  Итого личных долгов: {_fmt_usd(total_i_owe)}")

    parts.append("Должны мне:")
    total_owed = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("person_owes_me"):
        parts.append(f"  - {name}: {_fmt_usd(amount)}")
        total_owed += amount
    parts.append(f"  Итого должны мне: {_fmt_usd(total_owed)}")

    return "\n".join(parts)


# ──────────────────────────────────────────────────
# Изменение
# ──────────────────────────────────────────────────
def _find_debt(name: str, category: str = None):
    """Ищет долг по нечёткому совпадению имени. Возвращает (id, category, name, amount, currency) или None."""
    name_l = (name or "").lower().strip()
    if not name_l:
        return None
    if category:
        db.cursor.execute(
            "SELECT id, category, name, amount, currency FROM debts WHERE category=?",
            (category,)
        )
    else:
        db.cursor.execute("SELECT id, category, name, amount, currency FROM debts")
    rows = db.cursor.fetchall()

    # Точное вхождение в обе стороны
    for row in rows:
        db_name = row[2].lower()
        if name_l in db_name or db_name in name_l:
            return row
    # Совпадение по первому слову (Анорбанк, Pulinform, Сирож...)
    first = name_l.split()[0]
    for row in rows:
        if first and first in row[2].lower():
            return row
    return None


def update_debt_amount(name: str, new_amount: float, currency: str = None) -> str | None:
    """Меняет сумму долга на новую. Возвращает текст ответа или None если не нашёл."""
    row = _find_debt(name)
    if row is None:
        return None
    debt_id, category, db_name, old_amount, db_curr = row
    db.cursor.execute(
        "UPDATE debts SET amount=?, updated_at=? WHERE id=?",
        (new_amount, str(datetime.now()), debt_id)
    )
    db.conn.commit()

    fmt = _fmt_uzs if db_curr == "UZS" else _fmt_usd
    return (
        f"✏️ *Долг обновлён*\n\n"
        f"📌 {db_name}\n"
        f"Было: {fmt(old_amount)}\n"
        f"Стало: *{fmt(new_amount)}*"
    )


def reduce_debt(name: str, repaid_amount: float, currency: str = "USD") -> float | None:
    """Уменьшает долг при погашении. Возвращает новый остаток или None если не нашёл.

    Конвертирует в валюту долга при необходимости (курс 1$ = 12 000 сум).
    """
    row = _find_debt(name, "person_i_owe") or _find_debt(name, "bank")
    if row is None:
        return None
    debt_id, category, db_name, old_amount, db_curr = row

    # Приводим погашение к валюте долга
    if currency == db_curr:
        repaid = repaid_amount
    elif currency == "UZS" and db_curr == "USD":
        repaid = round(repaid_amount / 12000, 2)
    elif currency == "USD" and db_curr == "UZS":
        repaid = round(repaid_amount * 12000, 0)
    else:
        repaid = repaid_amount

    new_amount = round(max(old_amount - repaid, 0), 2)
    db.cursor.execute(
        "UPDATE debts SET amount=?, updated_at=? WHERE id=?",
        (new_amount, str(datetime.now()), debt_id)
    )
    db.conn.commit()
    return new_amount
