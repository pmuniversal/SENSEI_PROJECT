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
import urllib.request
import json

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
    ("person_owes_me", "Лазиз (брат)", 600,  "USD", "", "", 3),
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


def get_usd_rate() -> tuple[float, str]:
    """Получает курс продажи USD из Ипак йули банка (официальный сайт).
    Возвращает (курс_продажи, источник_строка).
    При недоступности сайта — ЦБ РУз как запасной вариант.
    """
    # 1. Парсим сайт Ипак йули напрямую
    try:
        url = "https://ipakyulibank.uz"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )
        html = urllib.request.urlopen(req, timeout=6).read().decode("utf-8", errors="ignore")
        # Ищем паттерн курса в таблице: "$ AQSh dollar | 12 040 | 12 140"
        # или числа после "USD" рядом друг с другом
        import re as _re
        # Ищем два числа вида 1xxxx подряд (покупка | продажа)
        matches = _re.findall(r'1[12]\s*[\s,.]?\s*\d{3}', html.replace('\xa0', ' '))
        # Берём уникальные числа, убираем пробелы
        nums = []
        for m in matches:
            n = int(_re.sub(r'[\s.,]', '', m))
            if 10000 < n < 20000 and n not in nums:
                nums.append(n)
        if len(nums) >= 2:
            # Первое — покупка, второе — продажа
            sell = nums[1]
            return float(sell), f"Ипак йули (касса, продажа): {sell:,} сум/$"
        elif len(nums) == 1:
            return float(nums[0]), f"Ипак йули: {nums[0]:,} сум/$"
    except Exception as e:
        print(f"[DEBTS] Ипак йули недоступен: {e}")

    # 2. Запасной: ЦБ РУз API
    try:
        url = "https://cbu.uz/en/arkhiv-kursov-valyut/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read().decode())
        for item in data:
            if item.get("Ccy") == "USD":
                rate = float(item["Rate"])
                return rate, f"ЦБ РУз: {rate:,.0f} сум/$"
    except Exception as e:
        print(f"[DEBTS] ЦБ РУз недоступен: {e}")

    return 12800.0, "резервный курс: 12 800 сум/$"


def get_debts_summary_text() -> str:
    """Формирует читаемую сводку долгов ИЗ БАЗЫ ДАННЫХ с итогами в сумах и долларах."""
    usd_rate, rate_source = get_usd_rate()
    lines = []

    # ── Кому ТЫ должен: Банки ────────────────────────
    lines.append("💳 *Кому я должен:*\n")
    lines.append("🏦 Банки:")
    total_bank_uzs = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("bank"):
        rate_str = f" ({rate})" if rate else ""
        note_str = f" {note}" if note else ""
        lines.append(f"  • {name} — *{_fmt_uzs(amount)}*{rate_str}{note_str}")
        total_bank_uzs += amount
    total_bank_usd = round(total_bank_uzs / usd_rate)
    lines.append(f"\n📊 Итого банков: *{_fmt_uzs(total_bank_uzs)}* ≈ *${total_bank_usd:,}*")

    # ── Кому ТЫ должен: Люди ─────────────────────────
    lines.append("")
    lines.append("👥 Люди (я должен им):")
    total_i_owe_usd = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("person_i_owe"):
        note_str = f" {note}" if note else ""
        lines.append(f"  • {name} — *{_fmt_usd(amount)}*{note_str}")
        total_i_owe_usd += amount
    total_i_owe_uzs = round(total_i_owe_usd * usd_rate)
    lines.append(f"\n📊 Итого людям: *{_fmt_usd(total_i_owe_usd)}* ≈ *{_fmt_uzs(total_i_owe_uzs)}*")

    # ── ОБЩИЙ ИТОГ ────────────────────────────────────
    grand_total_uzs = total_bank_uzs + total_i_owe_uzs
    grand_total_usd = round(grand_total_uzs / usd_rate)
    lines.append("")
    lines.append(f"💀 *ОБЩИЙ ДОЛГ: {_fmt_uzs(grand_total_uzs)}* ≈ *${grand_total_usd:,}*")
    lines.append(f"_📈 {rate_source}_")

    # ── Кто должен ТЕБЕ ─────────────────────────────
    lines.append("")
    lines.append("💰 *Кто должен мне:*\n")
    total_owed_usd = 0.0
    for _, name, amount, curr, rate, note in get_all_debts("person_owes_me"):
        lines.append(f"  • {name} — *{_fmt_usd(amount)}*")
        total_owed_usd += amount
    total_owed_uzs = round(total_owed_usd * usd_rate)
    lines.append(f"\n📊 Итого должны мне: *{_fmt_usd(total_owed_usd)}* ≈ *{_fmt_uzs(total_owed_uzs)}*")

    return "\n".join(lines)


def get_debts_for_prompt() -> str:
    """Компактная сводка долгов для подстановки в системный промпт AI."""
    try:
        usd_rate, rate_source = get_usd_rate()
    except Exception:
        usd_rate, rate_source = 12800.0, "резервный курс"
    parts = ["ТЕКУЩИЕ ДОЛГИ (актуально из базы, всегда опирайся на эти цифры):"]
    parts.append(f"Курс: {rate_source}")

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


def add_debt(category: str, name: str, amount: float, currency: str,
             rate: str = "", note: str = "") -> str:
    """Добавляет новую запись долга."""
    db.cursor.execute("SELECT MAX(sort_order) FROM debts WHERE category=?", (category,))
    row = db.cursor.fetchone()
    order = (row[0] or 0) + 1
    db.cursor.execute("""
    INSERT INTO debts (category, name, amount, currency, rate, note, sort_order, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (category, name, amount, currency, rate, note, order, str(datetime.now())))
    db.conn.commit()
    fmt = _fmt_uzs if currency == "UZS" else _fmt_usd
    return f"✅ *Добавлен долг*\n\n📌 {name}: {fmt(amount)}"


def rename_debt(old_name: str, new_name: str) -> str | None:
    """Переименовывает долг."""
    row = _find_debt(old_name)
    if row is None:
        return None
    debt_id = row[0]
    db.cursor.execute(
        "UPDATE debts SET name=?, updated_at=? WHERE id=?",
        (new_name, str(datetime.now()), debt_id)
    )
    db.conn.commit()
    return f"✏️ Переименовано: *{old_name}* → *{new_name}*"


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
