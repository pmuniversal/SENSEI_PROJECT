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
    Через GPT определяет тип сообщения и извлекает структурированные данные.
    Возвращает dict с полями:
      - type: 'task' | 'reminder' | 'query' | 'chat'
      - sphere: 'pulinform' | 'youtube' | 'services' | 'life' | null
      - task_text: текст задачи (если type=task)
      - remind_time: время напоминания ISO (если type=reminder)
      - remind_text: текст напоминания
      - query_sphere: сфера для запроса задач (если type=query)
    """
    now = datetime.now()
    system_prompt = f"""Ты — классификатор сообщений для личного ассистента.
Текущая дата и время: {now.strftime('%Y-%m-%d %H:%M')}

Определи тип сообщения пользователя и извлеки данные. Верни ТОЛЬКО JSON:

Если это ЗАДАЧА (содержит слова: задача, сделать, нужно, создать, запустить, купить, дедлайн):
{{"type": "task", "sphere": "youtube|pulinform|services|life|null", "task_text": "текст задачи", "deadline": "YYYY-MM-DD или null"}}

Если это НАПОМИНАНИЕ (содержит слова: напомни, напоминание, remind, через X часов/дней, в такое-то время, N числа):
{{"type": "reminder", "sphere": "youtube|pulinform|services|life|null", "remind_time": "YYYY-MM-DD HH:MM", "remind_text": "о чём напомнить"}}

Если это ЗАПРОС ЗАДАЧ (что у меня по..., покажи задачи, мои задачи):
{{"type": "query", "query_sphere": "youtube|pulinform|services|life|all"}}

Если это ОБЫЧНЫЙ РАЗГОВОР/ВОПРОС (всё остальное):
{{"type": "chat"}}

Правила определения сферы:
- pulinform: работа, взыскание, коллектор, Pulinform
- youtube: ютуб, YouTube, канал, видео, контент, ниша
- services: сайт, SaaS, услуги, бизнес, клиент, HVAC, plumber
- life: жизнь, быт, дом, семья, здоровье

Если сфера неясна — поставь null.
Верни ТОЛЬКО JSON, без комментариев и markdown."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
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
    Обрабатывает умный ввод. Возвращает:
      - None если это обычный чат (пусть AI обработает)
      - Строку с ответом если это задача/напоминание/запрос
    """
    result = classify_message(text)
    msg_type = result.get("type", "chat")

    if msg_type == "task":
        task_text = result.get("task_text", text)
        sphere = result.get("sphere")
        deadline = result.get("deadline")

        # Добавляем сферу в текст задачи если она определена
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

    elif msg_type == "reminder":
        remind_time = result.get("remind_time", "")
        remind_text = result.get("remind_text", text)

        if not remind_time:
            return None  # Не удалось определить время — пусть AI разберётся

        normalized = add_reminder(user_id, remind_time, remind_text)
        return f"⏰ Напоминание сохранено:\n\n{remind_text}\n📅 Когда: {normalized}"

    elif msg_type == "query":
        query_sphere = result.get("query_sphere", "all")
        rows = list_tasks(user_id)

        if not rows:
            return "📌 Нет активных задач."

        # Фильтруем по сфере если указана
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

    # type == "chat" — проверяем трекеры (сон/вес/дофамин/привычки)
    from bot.services.trackers import process_tracker
    tracker_result = process_tracker(user_id, text)
    if tracker_result:
        return tracker_result

    # Не трекер и не задача — вернуть None, пусть AI обработает как обычно
    return None
