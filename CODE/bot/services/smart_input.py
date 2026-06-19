"""
smart_input.py — Умный ввод: человеческий язык вместо команд (Этап 3)
======================================================================

Бот сам определяет: это разговор, задача или напоминание.
Примеры:
  - «в сфере ютуба задача создать канал, дедлайн 10 июня» → задача в сферу YouTube
  - «напомни 10 числа открыть канал» → напоминание
  - «что у меня по ютубу?» → показать задачи этой сферы
  - обычный текст → диалог с AI

Старые команды (/task, /tasks, /remind) остаются как запасной вариант.
"""

import json
import re
from datetime import datetime

from bot.services.ai import client
from bot.services.tasks import add_task, list_tasks
from bot.services.reminders import add_reminder

# 4 сферы пользователя
SPHERES = {
    "pulinform": ["pulinform", "работа", "ish", "взыскание", "коллектор"],
    "youtube": ["ютуб", "youtube", "канал", "видео", "контент", "ниша"],
    "services": ["сайт", "услуги", "saas", "бизнес", "клиент", "hvac", "plumber", "сантехник"],
    "life": ["жизнь", "быт", "дом", "семья", "здоровье", "личное"],
}


def classify_message(text: str) -> dict:
    """
    Единый умный классификатор через GPT-4o-mini.
    Понимает сокращения, опечатки, полуслова, смешанные языки (рус/узб/англ).
    Возвращает dict с полем type и нужными данными.
    """
    now = datetime.now()
    system_prompt = f"""Ты — умный классификатор команд личного ассистента Сенсей.
Текущая дата и время: {now.strftime('%Y-%m-%d %H:%M')}
Пользователь — Бекзод (узбек, пишет на русском, иногда добавляет узбекские/английские слова).

ВАЖНО: Понимай сокращения, опечатки, полуслова, неформальный язык.
Например: "гугл тбл" = Google Sheets, "обнови тблцу" = обновить таблицу,
"напомн завтра" = напоминание, "долги" = показать долги и т.д.

Верни ТОЛЬКО JSON одного из этих типов:

1. ФИНАНСОВЫЕ ОПЕРАЦИИ (деньги, траты, долги, кредиты, таблица):
{{"type": "finance", "text": "{text}"}}
Примеры: "потратил 50к на еду", "долг анорбанк", "покажи долги", "обнови гугл таблицу",
"синхронизируй таблицу", "отдал 100$ сирожу", "измени долг pulinform на 30 млн",
"баланс", "расходы за месяц", "заработал 500$"

2. ТРЕКЕРЫ (сон, вес, привычки, дофамин):
{{"type": "tracker", "text": "{text}"}}
Примеры: "спал 7 часов", "вес 82", "залипал в тикток 2 часа", "привычки", "стрик"

3. ЗАДАЧА (что-то нужно сделать, создать, запустить):
{{"type": "task", "sphere": "youtube|pulinform|services|life|null", "task_text": "текст", "deadline": "YYYY-MM-DD или null"}}
Примеры: "задача сделать сайт", "нужно позвонить клиенту", "создать канал на ютубе дедлайн 1 июля"

4. НАПОМИНАНИЕ:
{{"type": "reminder", "sphere": "youtube|pulinform|services|life|null", "remind_time": "YYYY-MM-DD HH:MM", "remind_text": "текст"}}
Примеры: "напомни 25го заплатить аренду", "напомни через 2 часа позвонить"

5. ЗАПРОС ЗАДАЧ:
{{"type": "query", "query_sphere": "youtube|pulinform|services|life|all"}}
Примеры: "что у меня по ютубу", "покажи задачи", "мои задачи по работе"

6. БАЗА ЗНАНИЙ:
{{"type": "knowledge", "text": "{text}"}}
Примеры: "запомни что...", "что я знаю о...", "база знаний"

7. ОБЫЧНЫЙ РАЗГОВОР (всё что не попало выше):
{{"type": "chat"}}

Сферы: pulinform=работа/взыскание, youtube=ютуб/канал/видео, services=сайт/saas/бизнес/USA, life=быт/семья/здоровье
Верни ТОЛЬКО JSON без объяснений."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    # Убираем markdown если есть
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"type": "chat"}


def process_smart_input(user_id, text: str, bot=None, message=None) -> str | None:
    """
    Единая точка входа умного ввода.
    Классификатор определяет тип → роутим в нужный обработчик.
    Возвращает None только для обычного чата.
    """
    result = classify_message(text)
    msg_type = result.get("type", "chat")

    # Финансовые операции → finance.py
    if msg_type == "finance":
        from bot.services.finance import process_finance
        fin_result = process_finance(user_id, result.get("text", text))
        if fin_result is not None:
            return fin_result
        # GPT решил что финансовое, но парсер не распознал → в AI
        return None

    # Трекеры → trackers.py
    if msg_type == "tracker":
        from bot.services.trackers import process_tracker
        tracker_result = process_tracker(user_id, result.get("text", text))
        if tracker_result is not None:
            return tracker_result
        return None

    # База знаний → knowledge.py
    if msg_type == "knowledge":
        from bot.services.knowledge import process_knowledge
        knowledge_result = process_knowledge(user_id, result.get("text", text))
        if knowledge_result:
            return knowledge_result
        return None

    # Задача
    if msg_type == "task":
        task_text = result.get("task_text", text)
        sphere = result.get("sphere")
        deadline = result.get("deadline")

        prefix = ""
        if sphere and sphere != "null":
            sphere_names = {
                "pulinform": "Pulinform",
                "youtube": "YouTube",
                "services": "Услуги/SaaS",
                "life": "Жизнь/быт",
            }
            prefix = f"[{sphere_names.get(sphere, sphere)}] "

        full_task = f"{prefix}{task_text}"
        if deadline and deadline != "null":
            full_task += f" (дедлайн: {deadline})"

        add_task(user_id, full_task)
        return f"✅ Задача добавлена:\n\n{full_task}"

    # Напоминание
    if msg_type == "reminder":
        remind_time = result.get("remind_time", "")
        remind_text = result.get("remind_text", text)

        if not remind_time:
            return None

        normalized = add_reminder(user_id, remind_time, remind_text)
        return f"⏰ Напоминание сохранено:\n\n{remind_text}\n📅 Когда: {normalized}"

    # Запрос задач
    if msg_type == "query":
        query_sphere = result.get("query_sphere", "all")
        rows = list_tasks(user_id)

        if not rows:
            return "📌 Нет активных задач."

        if query_sphere and query_sphere != "all":
            sphere_names = {
                "pulinform": "Pulinform",
                "youtube": "YouTube",
                "services": "Услуги/SaaS",
                "life": "Жизнь/быт",
            }
            filter_tag = sphere_names.get(query_sphere, query_sphere)
            filtered = [(id_, task) for id_, task in rows if filter_tag.lower() in task.lower()]
            if filtered:
                rows = filtered

        result_text = f"📌 Задачи ({query_sphere if query_sphere != 'all' else 'все'}):\n\n"
        for row in rows:
            result_text += f"{row[0]}. {row[1]}\n"

        return result_text

    # chat → вернуть None, пусть AI обработает
    return None
