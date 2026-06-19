"""
webhook_deploy.py — Автодеплой при git push
=============================================
Слушает POST-запросы от GitHub Webhook на порту 9000.
При получении push-события — скачивает изменённые файлы
из GitHub и перезапускает бота.

Запуск (добавлен в supervisord.conf автоматически):
  python3 /app/webhook_deploy.py
"""

import hmac
import hashlib
import json
import os
import subprocess
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ── Конфиг ─────────────────────────────────────────
PORT = 9000
GITHUB_RAW = "https://raw.githubusercontent.com/pmuniversal/SENSEI_PROJECT/main/CODE"
APP_DIR = "/app"
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "sensei-deploy-2026")

# Файлы которые нужно обновлять при деплое
DEPLOY_FILES = [
    ("bot/services/ai.py",          f"{APP_DIR}/bot/services/ai.py"),
    ("bot/services/finance.py",     f"{APP_DIR}/bot/services/finance.py"),
    ("bot/services/debts.py",       f"{APP_DIR}/bot/services/debts.py"),
    ("bot/services/smart_input.py", f"{APP_DIR}/bot/services/smart_input.py"),
    ("bot/services/trackers.py",    f"{APP_DIR}/bot/services/trackers.py"),
    ("bot/services/reminders.py",   f"{APP_DIR}/bot/services/reminders.py"),
    ("bot/services/proactive.py",   f"{APP_DIR}/bot/services/proactive.py"),
    ("bot/services/profile.py",     f"{APP_DIR}/bot/services/profile.py"),
    ("bot/services/memory.py",      f"{APP_DIR}/bot/services/memory.py"),
    ("bot/services/sheets.py",      f"{APP_DIR}/bot/services/sheets.py"),
    ("bot/services/meeting.py",     f"{APP_DIR}/bot/services/meeting.py"),
    ("bot/services/voice_processor.py", f"{APP_DIR}/bot/services/voice_processor.py"),
    ("bot/handlers/text.py",        f"{APP_DIR}/bot/handlers/text.py"),
    ("bot/handlers/voice.py",       f"{APP_DIR}/bot/handlers/voice.py"),
    ("bot/handlers/commands.py",    f"{APP_DIR}/bot/handlers/commands.py"),
    ("bot/main.py",                 f"{APP_DIR}/bot/main.py"),
    ("bot/config.py",               f"{APP_DIR}/bot/config.py"),
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[DEPLOY {ts}] {msg}", flush=True)


def fetch_file(repo_path, local_path):
    """Скачивает файл из GitHub (без кеша)."""
    url = f"{GITHUB_RAW}/{repo_path}"
    req = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}
    )
    content = urllib.request.urlopen(req, timeout=15).read().decode()
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w") as f:
        f.write(content)
    return len(content)


def deploy(changed_files=None):
    """Скачивает обновлённые файлы и перезапускает бота."""
    log("Начинаю деплой...")
    updated = []
    errors = []

    for repo_path, local_path in DEPLOY_FILES:
        # Если список изменённых файлов передан — обновляем только их
        if changed_files and not any(repo_path in f for f in changed_files):
            continue
        try:
            size = fetch_file(repo_path, local_path)
            log(f"  OK {repo_path} ({size} bytes)")
            updated.append(repo_path)
        except Exception as e:
            log(f"  FAIL {repo_path}: {e}")
            errors.append(repo_path)

    if not updated and not errors:
        log("Нет файлов для обновления")
        return

    # Перезапускаем бота
    log("Перезапускаю бота...")
    try:
        result = subprocess.run(
            ["supervisorctl", "restart", "telegrambot"],
            capture_output=True, text=True, timeout=30
        )
        log(f"supervisorctl: {result.stdout.strip() or result.stderr.strip()}")
    except Exception as e:
        log(f"Ошибка перезапуска: {e}")

    log(f"Деплой завершён. Обновлено: {len(updated)}, ошибок: {len(errors)}")


def verify_signature(payload_body, signature_header):
    """Проверяет подпись GitHub Webhook."""
    if not signature_header:
        return False
    try:
        sha_name, signature = signature_header.split("=", 1)
        if sha_name != "sha256":
            return False
        mac = hmac.new(
            WEBHOOK_SECRET.encode(),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception:
        return False


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Отключаем стандартный HTTP-лог

    def do_GET(self):
        """Healthcheck endpoint."""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sensei Deploy Server OK")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        payload_body = self.rfile.read(content_length)

        # Проверяем подпись
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload_body, signature):
            log("WARN: Неверная подпись webhook — игнорирую")
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

        # Парсим payload
        try:
            payload = json.loads(payload_body.decode())
            event = self.headers.get("X-GitHub-Event", "")

            if event == "push":
                commits = payload.get("commits", [])
                changed = []
                for commit in commits:
                    changed += commit.get("added", [])
                    changed += commit.get("modified", [])
                log(f"Push event. Изменённых файлов: {len(changed)}")
                # Запускаем деплой в фоне
                import threading
                threading.Thread(
                    target=deploy,
                    args=(changed if changed else None,),
                    daemon=True
                ).start()
            else:
                log(f"Событие {event} — пропускаю")
        except Exception as e:
            log(f"Ошибка парсинга payload: {e}")


if __name__ == "__main__":
    log(f"Запуск deploy-сервера на порту {PORT}")
    log(f"Secret: {'настроен' if WEBHOOK_SECRET else 'НЕ НАСТРОЕН'}")
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    server.serve_forever()
