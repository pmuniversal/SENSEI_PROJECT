"""
finance.py — Личный финансист (Этап 5)
=======================================

Возможности:
  - Ввод доходов/расходов человеческим языком (текст + голос)
  - Хранение: сумма, тип, категория, сфера, дата, комментарий
  - Запросы: баланс, отчёт за период, топ расходов
  - Поддержка мультивалюты: UZS, USD
  - Предупреждения о нежелательных тратах

Примеры ввода:
  «потратил 50000 сум налички на еду»
  «заработал 500 долларов с YouTube»
  «за 300к купил жене одежду»
  «мой баланс», «сколько потратил в этом месяце?»
"""

import json
import re
from datetime import datetime, date

from bot.database import db
from bot.services.ai import client


# ──────────────────────────────────────────────────
# Инициализация таблицы
# ──────────────────────────────────────────────────
def init_finance_table():
    db.cursor.execute("""
    CREATE TABLE IF NOT EXISTS finance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        type TEXT,          -- 'income' | 'expense' | 'debt_give' | 'debt_take'
        amount REAL,
        currency TEXT,      -- 'UZS' | 'USD' | 'RUB'
        category TEXT,      -- еда, одежда, транспорт, бизнес, зарплата, ...
        sphere TEXT,        -- pulinform | youtube | services | life
        comment TEXT,
        payment_method TEXT, -- наличные | карта | перевод
        created_at TEXT
    )
    """)
    db.conn.commit()


init_finance_table()


# ──────────────────────────────────────────────────
# Парсинг финансового ввода через GPT
# ──────────────────────────────────────────────────
def parse_finance_input(text: str) -> dict | None:
    """
    Парсит финансовое сообщение через GPT.
    Возвращает структурированный dict или None если не финансовое сообщение.
    """
    today = date.today().isoformat()
    system_prompt = f"""Ты — финансовый парсер. Текущая дата: {today}.

Если сообщение содержит финансовую операцию — верни JSON:
{{
  "type": "income|expense|debt_give|debt_take|debt_repay|query_balance|query_report|query_debts",
  "amount": число или null,
  "currency": "UZS|USD|RUB",
  "category": "категория или null",
  "sphere": "pulinform|youtube|services|life|null",
  "payment_method": "наличные|карта|перевод|null",
  "comment": "краткий комментарий",
  "period": "month|week|today|null",
  "person": "имя человека или null"
}}

Правила:
- income: заработал, получил, пришло, доход, выручка
- expense: потратил, купил, заплатил, расход, трата
- debt_give: одолжил, дал в долг (ТЫ дал — они будут должны тебе)
- debt_take: взял в долг, занял (ТЫ взял — ты должен им)
- debt_repay: отдал долг, вернул долг, погасил (ТЫ вернул СВОЙ долг)
  ПРИМЕРЫ debt_repay: "отдал 1$ Сирож ака", "вернул Истаму 100$", "отдал Ивану 50$"
  ВАЖНО: "отдал [сумму] [имя]" = debt_repay, НЕ debt_give!
- query_balance: мой баланс, сколько денег
- query_report: отчёт, сколько потратил (period: month/week/today)
- query_debts: покажи долги, список долгов, кому должен, кредиты, финансовая ситуация

- person: извлеки имя (Сирож ака, Истам, Иван, Илёс ака, Анорбанк, AVO и т.д.)
- Валюта: сум/UZS/к → UZS; $/доллар → USD; по умолчанию UZS
- к = тысяча, млн = миллион

Если НЕ финансовое — верни: {{"type": "none"}}
Верни ТОЛЬКО JSON."""

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=300,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if data.get("type") == "none":
            return None
        return data
    except Exception:
        return None


# ──────────────────────────────────────────────────
# Сохранение операции
# ──────────────────────────────────────────────────
def save_transaction(user_id, data: dict) -> str:
    """Сохраняет финансовую операцию и возвращает текст ответа."""
    now = str(datetime.now())
    t_type = data.get("type", "expense")
    amount = data.get("amount") or 0
    currency = data.get("currency", "UZS")
    category = data.get("category") or "другое"
    sphere = data.get("sphere") or "life"
    comment = data.get("comment") or ""
    method = data.get("payment_method") or "наличные"

    db.cursor.execute("""
    INSERT INTO finance (user_id, type, amount, currency, category, sphere, comment, payment_method, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(user_id), t_type, amount, currency, category, sphere, comment, method, now))
    db.conn.commit()

    # Форматируем сумму
    if currency == "UZS":
        amount_str = f"{amount:,.0f} сум".replace(",", " ")
    elif currency == "USD":
        amount_str = f"${amount:,.0f}".replace(",", " ")
    else:
        amount_str = f"{amount:,.0f} {currency}"

    type_emoji = {"income": "💰", "expense": "💸", "debt_give": "🤝", "debt_take": "📥"}
    type_name = {"income": "Доход", "expense": "Расход", "debt_give": "Долг (дал)", "debt_take": "Долг (взял)"}
    sphere_name = {"pulinform": "Pulinform", "youtube": "YouTube", "services": "Услуги", "life": "Жизнь/быт"}

    emoji = type_emoji.get(t_type, "💳")
    name = type_name.get(t_type, t_type)
    sphere_str = sphere_name.get(sphere, sphere)

    return (
        f"{emoji} *{name} записан*\n\n"
        f"💵 Сумма: {amount_str}\n"
        f"📂 Категория: {category}\n"
        f"🔷 Сфера: {sphere_str}\n"
        f"💳 Способ: {method}\n"
        f"💬 {comment}"
    )


# ──────────────────────────────────────────────────
# Запросы и отчёты
# ──────────────────────────────────────────────────
def get_balance(user_id) -> str:
    """Баланс: доходы - расходы."""
    db.cursor.execute("""
    SELECT type, currency, SUM(amount) FROM finance
    WHERE user_id=? AND type IN ('income','expense')
    GROUP BY type, currency
    """, (str(user_id),))
    rows = db.cursor.fetchall()

    if not rows:
        return "📊 Нет финансовых данных. Начни вводить расходы и доходы."

    totals = {}
    for t, curr, s in rows:
        if curr not in totals:
            totals[curr] = {"income": 0, "expense": 0}
        totals[curr][t] = totals[curr].get(t, 0) + (s or 0)

    lines = ["📊 *Баланс:*\n"]
    for curr, vals in totals.items():
        inc = vals.get("income", 0)
        exp = vals.get("expense", 0)
        bal = inc - exp
        curr_sym = "сум" if curr == "UZS" else ("$" if curr == "USD" else curr)
        sign = "+" if bal >= 0 else ""
        lines.append(
            f"*{curr}:*\n"
            f"  💰 Доходы: {inc:,.0f} {curr_sym}\n"
            f"  💸 Расходы: {exp:,.0f} {curr_sym}\n"
            f"  📈 Баланс: {sign}{bal:,.0f} {curr_sym}"
        )
    return "\n\n".join(lines).replace(",", " ")


def get_report(user_id, period: str = "month") -> str:
    """Отчёт за период."""
    today = date.today()
    if period == "today":
        from_date = today.isoformat()
        period_name = "сегодня"
    elif period == "week":
        from datetime import timedelta
        from_date = (today - timedelta(days=7)).isoformat()
        period_name = "неделю"
    else:  # month
        from_date = today.replace(day=1).isoformat()
        period_name = "этот месяц"

    db.cursor.execute("""
    SELECT type, currency, category, SUM(amount) as total
    FROM finance
    WHERE user_id=? AND created_at >= ?
    GROUP BY type, currency, category
    ORDER BY total DESC
    """, (str(user_id), from_date))
    rows = db.cursor.fetchall()

    if not rows:
        return f"📊 Нет данных за {period_name}."

    income_uzs, expense_uzs = 0, 0
    income_usd, expense_usd = 0, 0
    expense_by_cat = {}

    for t, curr, cat, total in rows:
        if t == "income":
            if curr == "USD": income_usd += total
            else: income_uzs += total
        elif t == "expense":
            if curr == "USD": expense_usd += total
            else: expense_uzs += total
            key = f"{cat or 'другое'} ({curr})"
            expense_by_cat[key] = expense_by_cat.get(key, 0) + total

    lines = [f"📊 *Отчёт за {period_name}:*\n"]
    if income_uzs: lines.append(f"💰 Доходы: {income_uzs:,.0f} сум")
    if income_usd: lines.append(f"💰 Доходы: ${income_usd:,.0f}")
    if expense_uzs: lines.append(f"💸 Расходы: {expense_uzs:,.0f} сум")
    if expense_usd: lines.append(f"💸 Расходы: ${expense_usd:,.0f}")

    if expense_by_cat:
        lines.append("\n*Топ расходов:*")
        for cat, total in sorted(expense_by_cat.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  • {cat}: {total:,.0f}")

    return "\n".join(lines).replace(",", " ")


def save_debt_repayment(user_id, data: dict) -> str:
    """Сохраняет погашение личного долга и обновляет Google Sheets."""
    now = str(datetime.now())
    amount = data.get("amount") or 0
    currency = data.get("currency", "USD")
    person = data.get("person") or data.get("comment") or "неизвестно"
    comment = data.get("comment") or f"погашение долга {person}"

    # Сохраняем в БД как расход (деньги ушли)
    db.cursor.execute("""
    INSERT INTO finance (user_id, type, amount, currency, category, sphere, comment, payment_method, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(user_id), "debt_repay", amount, currency, "погашение долга", "life", comment, "наличные", now))
    db.conn.commit()

    # Словарь: имя → текущий остаток в $
    personal_debt_balances = {
        "сирож ака": 600,
        "сирож":     600,
        "истам":     2287,
        "иван":      4920,
        "илёс ака":  100,
        "илёс":      100,
    }

    person_lower = person.lower().strip()
    new_balance = None
    matched_name = None

    for key, balance in personal_debt_balances.items():
        if key in person_lower or person_lower in key:
            # Конвертируем сумму если нужно (упрощённо: 1$ = 12700 сум)
            if currency == "UZS":
                repaid_usd = round(amount / 12700, 2)
            else:
                repaid_usd = amount
            new_balance = round(balance - repaid_usd, 2)
            matched_name = person
            break

    # Записываем в Google Sheets → История
    try:
        from bot.services.sheets import log_payment, sheets_manager, SHEET_CREDITS
        log_payment(
            credit_name=person,
            amount=amount,
            comment=f"погашение долга",
            new_balance=new_balance
        )

        # Обновляем остаток в листе Кредиты и долги если нашли имя
        if new_balance is not None and matched_name:
            sheets_manager.update_credit_balance(matched_name, new_balance)
    except Exception as e:
        print(f"[FINANCE] Ошибка обновления Sheets: {e}")

    # Форматируем ответ
    if currency == "USD":
        amount_str = f"${amount}"
    else:
        amount_str = f"{amount:,.0f} сум"

    balance_str = ""
    if new_balance is not None:
        balance_str = f"\n📉 Остаток долга {person}: *${new_balance:,.2f}*"

    return (
        f"✅ *Погашение долга записано*\n\n"
        f"👤 Кому: {person}\n"
        f"💵 Сумма: {amount_str}\n"
        f"📊 Записано в Google Sheets (История + Кредиты и долги)"
        f"{balance_str}"
    )


# ──────────────────────────────────────────────────
    """Показывает сводку всех кредитов и личных долгов."""
    lines = ["💳 *Мои кредиты и долги:*\n"]

    # Банковские кредиты
    lines.append("🏦 *Банки:*")
    bank_debts = [
        ("Анорбанк №1",             "17,545,179 сум", "42%", "04.02.2027", ""),
        ("Анорбанк №2",             "16,240,921 сум", "47%", "14.10.2027", "⚠️ просрочка"),
        ("AVO карта",               "23,510,000 сум", "45%+", "-",         "весь лимит"),
        ("Узумбанк микрозайм",      "22,000,000 сум", "44%", "-",          "⚠️ просрочка"),
        ("Юрлица (гос.)",           "~95,000,000 сум","23%", "2027",       "🔴 КРИТИЧНО"),
        ("Pulinform рассрочка",     "25,000,000 сум", "0%",  "10.07.2026+","беспроц."),
    ]
    total_bank = 0
    for name, balance, rate, until, note in bank_debts:
        note_str = f" — {note}" if note else ""
        lines.append(f"  • {name}: *{balance}* ({rate}){note_str}")

    lines.append("")
    lines.append("👥 *Личные долги (людям):*")
    personal_debts = [
        ("Сирож ака", "$600",   "до 10.07.2026", "🔴 СРОЧНО"),
        ("Истам",     "$2,287", "срочный",        "⚠️ приоритет"),
        ("Иван",      "$4,920", "не срочный",     ""),
        ("Илёс ака",  "$100",   "-",              ""),
    ]
    total_usd = 600 + 2287 + 4920 + 100
    for name, amount, deadline, note in personal_debts:
        note_str = f" {note}" if note else ""
        lines.append(f"  • {name}: *{amount}* ({deadline}){note_str}")

    lines.append(f"\n💰 *Итого личных долгов: ${total_usd:,}*")
    lines.append("\n📊 Полная таблица → Google Sheets «Кредиты и долги»")
    return "\n".join(lines)


def get_debts_summary() -> str:
    """Показывает кому ты должен и кто должен тебе — точный список."""
    lines = []

    # ── Кому ТЫ должен ──────────────────────────────
    lines.append("💳 *Кому я должен:*\n")
    lines.append("🏦 Банки:")
    lines.append("  • Анорбанк №1 — *17 545 179 сум* (42%)")
    lines.append("  • Анорбанк №2 — *16 240 921 сум* (47%) ⚠️ просрочка")
    lines.append("  • AVO карта — *23 510 000 сум* (45%+)")
    lines.append("  • Узумбанк — *22 000 000 сум* (44%) ⚠️ просрочка")
    lines.append("  • Юрлица (гос.) — *~95 000 000 сум* 🔴 КРИТИЧНО до 30.06")
    lines.append("  • Pulinform рассрочка — *25 000 000 сум* (0%)")
    lines.append("")
    lines.append("👥 Люди (я должен им):")
    lines.append("  • Сирож ака — *$600* (до 10.07.2026) 🔴 СРОЧНО")
    lines.append("  • Навруз — *$1 600* ⚠️ срочный")
    lines.append("  • Истам — *$2 287* ⚠️ приоритет")
    lines.append("  • Иван — *$4 920* (не срочный)")
    lines.append("  • Илёс ака — *$100*")
    lines.append("")
    lines.append("📊 Итого личных долгов: *$9 507*")

    # ── Кто должен ТЕБЕ ─────────────────────────────
    lines.append("")
    lines.append("💰 *Кто должен мне:*\n")
    lines.append("  • Навруз — *$1 600*")
    lines.append("  • Умар — *$200*")
    lines.append("  • Лазиз (брат) — *$300*")
    lines.append("")
    lines.append("📊 Итого должны мне: *$2 100*")

    return "\n".join(lines)


# ──────────────────────────────────────────────────
# Главная функция — обработка финансового текста
# ──────────────────────────────────────────────────
def process_finance(user_id, text: str) -> str | None:
    """
    Обрабатывает финансовый ввод.
    Возвращает ответ или None если не финансовое.
    """
    data = parse_finance_input(text)
    if data is None:
        return None

    t = data.get("type")

    if t in ("income", "expense", "debt_give", "debt_take"):
        return save_transaction(user_id, data)
    elif t == "debt_repay":
        return save_debt_repayment(user_id, data)
    elif t == "query_balance":
        return get_balance(user_id)
    elif t == "query_report":
        period = data.get("period") or "month"
        return get_report(user_id, period)
    elif t == "query_debts":
        return get_debts_summary()

    return None
