# ERRORS_LOG — Журнал ошибок — Sensei

> Новые записи добавляются СВЕРХУ. Записи не удаляются.
> Читать при старте сессии и перед началом новой задачи.
> Формат: [YYYY-MM-DD] [категория] — суть → решение → как не повторить

---

# ERRORS_LOG — Журнал ошибок — Sensei

> Новые записи добавляются СВЕРХУ. Записи не удаляются.
> Читать при старте сессии и перед началом новой задачи.
> Формат: [YYYY-MM-DD] [категория] — суть → решение → как не повторить

---

## [2026-06-19] [AI/МОДЕЛИ] — GPT-5 mini падал молча, бот уходил на Gemini

**Суть:** После смены основной модели на gpt-5-mini бот продолжал отвечать через Gemini. GPT-5 модели (gpt-5, gpt-5-mini, gpt-5-nano и новее) НЕ принимают параметр `max_tokens` — выдают ошибку 400 `Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.` Ошибка ловилась в try/except и бот молча переключался на резервную модель.

**Решение:** Для GPT-5 моделей использовать `max_completion_tokens` вместо `max_tokens`:
```python
response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=messages,
    max_completion_tokens=2000,   # НЕ max_tokens!
)
```

**Как не повторить:** Для всех GPT-5 и o-series моделей — только `max_completion_tokens`. Старые модели (gpt-4.1, gpt-4o-mini, gpt-4.1-mini) принимают `max_tokens` как обычно. При смене модели на GPT-5 ВСЕГДА менять и параметр.

---

## [2026-06-19] [ДЕПЛОЙ] — приватный репозиторий отдаёт 404 вместо файла

**Суть:** raw.githubusercontent.com на приватном репо возвращает HTML `404: Not Found`. urllib записывает этот текст в .py файл → бот падает с `SyntaxError: illegal target for annotation` в строке 1.

**Решение:** Перед деплоем сделать репозиторий публичным (GitHub → Settings → Danger Zone → Change visibility → Public), скачать файлы, затем вернуть Private.

**Как не повторить:** Всегда делать репо публичным на время деплоя через raw.githubusercontent. После проверки `OK: NNNNN bytes` (должно быть >1000 байт, не ~20 байт) — закрывать обратно.

---

## [2026-06-19] [ДЕПЛОЙ] — неверная команда для просмотра логов supervisor

**Суть:** Дал команду `tail -30 /var/log/supervisor/telegrambot.log` — файл не существует в этом контейнере. Получили ошибку `No such file or directory`.

**Решение:** Правильная команда для просмотра логов через supervisorctl:
```bash
supervisorctl tail telegrambot
```

**Как не повторить:** В этом контейнере логи supervisor читаются ТОЛЬКО через `supervisorctl tail telegrambot`. Путь `/var/log/supervisor/` не существует. Всегда использовать supervisorctl.

---

## [2026-06-18] [ДЕПЛОЙ] — curl не обновляет файлы на сервере

**Суть:** `curl -o /app/bot/services/ai.py https://raw.githubusercontent.com/...` качает старую версию из кеша GitHub даже после push.

**Решение:** Использовать Python urllib с no-cache заголовком:
```bash
python3 -c "
import urllib.request
url = 'https://raw.githubusercontent.com/pmuniversal/SENSEI_PROJECT/main/CODE/bot/services/FILENAME.py'
req = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
content = urllib.request.urlopen(req).read().decode()
open('/app/bot/services/FILENAME.py', 'w').write(content)
print('OK:', len(content), 'bytes')
"
```

**Как не повторить:** Всегда использовать python3 urllib вместо curl для обновления файлов на сервере.

---

## [2026-06-18] [GROQ] — Groq бесплатный план превышает лимит токенов

**Суть:** llama-3.3-70b-versatile и llama-3.1-70b-versatile превышают 12000 TPM на бесплатном плане. Запрос с большим промптом (финансовые данные + история) = 12-14k токенов.

**Решение:** Использовать Gemini 2.0 Flash как основную модель (1M токенов контекста, бесплатно). Groq оставить как запасную с моделью llama-3.1-8b-instant.

**Как не повторить:** Не использовать Groq 70b модели с большими промптами на бесплатном плане.

---