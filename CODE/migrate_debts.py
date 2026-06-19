"""
migrate_debts.py — Миграция данных долгов на сервере
======================================================
Запускать ОДИН РАЗ после деплоя новых файлов:
  python3 /app/migrate_debts.py

Что делает:
  1. Создаёт таблицу debts если нет
  2. Наполняет начальными данными если пустая
  3. Применяет актуальные изменения от 19.06.2026
"""
import sys
import os
sys.path.insert(0, '/app')
os.environ.setdefault('SENSEI_DATA_DIR', '/app')

from bot.database import db
from bot.services.debts import (
    init_debts_table, seed_debts_if_empty,
    update_debt_amount, rename_debt, add_debt, reduce_debt, get_debts_summary_text
)
from datetime import datetime

print("=== Миграция долгов 19.06.2026 ===\n")
init_debts_table()
seed_debts_if_empty()

changes = []

# 1. Лазиз (брат): $300 → $600
res = update_debt_amount("Лазиз", 600, "USD")
changes.append(f"Лазиз: {res}")

# 2. Переименовать "Юрлица (гос.)" → "SQB Юрлица (гос.)" + долг 100 млн
res = rename_debt("Юрлица (гос.)", "SQB Юрлица (гос.)")
changes.append(f"Переименование: {res}")
res2 = update_debt_amount("SQB Юрлица", 100000000, "UZS")
changes.append(f"SQB долг: {res2}")

# 3. Добавить нового должника: Ойбек ака (кв. хозяин) — $150
db.cursor.execute("SELECT id FROM debts WHERE name LIKE '%Ойбек%'")
if not db.cursor.fetchone():
    res = add_debt("person_i_owe", "Ойбек ака (кв. хозяин)", 150, "USD", "", "")
    changes.append(f"Новый долг: {res}")
else:
    changes.append("Ойбек ака — уже есть")

# 4. Узумбанк: обновить сумму (взял 2млн, закрыл просрочку 920к, лимит теперь 2млн)
# Текущий остаток Узумбанк ≈ 22 млн → -920к просрочка = 21 080 000, но взял ещё 2 млн → 23 080 000
# Реальный остаток по лимиту: взял 22 млн из 25 млн, теперь лимит 2 млн → взято ~23 млн из 25 млн
db.cursor.execute("SELECT amount FROM debts WHERE name LIKE '%Узум%'")
row = db.cursor.fetchone()
if row:
    current = row[0]
    # +2 млн взял, -920к погасил просрочку = нетто +1 080 000
    new_amount = current + 1080000
    res = update_debt_amount("Узумбанк", new_amount, "UZS")
    # Обновляем примечание
    db.cursor.execute("UPDATE debts SET note=? WHERE name LIKE '%Узум%'",
                      ("⚠️ лимит использован, остаток 2 млн",))
    db.conn.commit()
    changes.append(f"Узумбанк: {res}")

for c in changes:
    print(c)

print("\n=== Итоговая сводка ===")
print(get_debts_summary_text())
print("\n=== Миграция завершена ===")
