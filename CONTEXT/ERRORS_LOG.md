# ERRORS_LOG — Журнал ошибок — Sensei

> Новые записи добавляются СВЕРХУ. Записи не удаляются.
> Читать при старте сессии и перед началом новой задачи.
> Формат: [YYYY-MM-DD] [категория] — суть → решение → как не повторить

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