"""
sheets.py — Интеграция с Google Sheets для ведения финансов
===========================================================

Два листа:
1. "Кредиты и долги" — сводка всех кредитов и долгов (остатки, ставки, просрочки)
2. "История" — каждый платёж с датой, суммой, комментарием

Бот автоматически обновляет таблицы при упоминании платежей.
"""

import os
from datetime import datetime
from typing import Optional

try:
    from google.oauth2.service_account import Credentials
    import googleapiclient.discovery
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    print("[SHEETS] google-auth-oauthlib не установлен")

# Константы имён листов
SHEET_CREDITS = "Кредиты и долги"
SHEET_HISTORY = "История"


class SheetsManager:
    """Менеджер Google Sheets для финансов Бекзода."""

    def __init__(self):
        self.service = None
        self.sheet_id = os.getenv("GOOGLE_SHEETS_ID")
        self.creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "/app/google_credentials.json")
        self._init_service()

    def _init_service(self):
        """Инициализирует Google Sheets API сервис."""
        if not SHEETS_AVAILABLE or not self.sheet_id:
            return

        try:
            if not os.path.exists(self.creds_path):
                print(f"[SHEETS] Файл {self.creds_path} не найден")
                return

            credentials = Credentials.from_service_account_file(
                self.creds_path,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            self.service = googleapiclient.discovery.build("sheets", "v4", credentials=credentials)
            print("[SHEETS] Инициализирована успешно")
        except Exception as e:
            print(f"[SHEETS] Ошибка инициализации: {e}")

    def _get_all_sheets(self) -> dict:
        """Возвращает словарь {название: sheetId} всех листов."""
        try:
            meta = self.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            return {s["properties"]["title"]: s["properties"]["sheetId"]
                    for s in meta.get("sheets", [])}
        except Exception:
            return {}

    def _get_sheet_id(self, sheet_name: str) -> Optional[int]:
        """Возвращает числовой sheetId по имени листа."""
        sheets = self._get_all_sheets()
        return sheets.get(sheet_name)

    def _ensure_sheets(self):
        """Создаёт или переименовывает листы до нужных имён."""
        if not self.service or not self.sheet_id:
            return

        try:
            sheets = self._get_all_sheets()
            requests = []

            # Переименовываем старый лист «Кредиты» если он есть
            if "Кредиты" in sheets and SHEET_CREDITS not in sheets:
                requests.append({
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheets["Кредиты"],
                            "title": SHEET_CREDITS
                        },
                        "fields": "title"
                    }
                })
                print(f"[SHEETS] Переименован лист 'Кредиты' → '{SHEET_CREDITS}'")

            # Создаём листы если их нет
            if SHEET_CREDITS not in sheets and "Кредиты" not in sheets:
                requests.append({
                    "addSheet": {
                        "properties": {"title": SHEET_CREDITS,
                                       "gridProperties": {"rowCount": 100}}
                    }
                })
            if SHEET_HISTORY not in sheets:
                requests.append({
                    "addSheet": {
                        "properties": {"title": SHEET_HISTORY,
                                       "gridProperties": {"rowCount": 1000}}
                    }
                })

            if requests:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={"requests": requests}
                ).execute()
                print("[SHEETS] Листы готовы")
        except Exception as e:
            print(f"[SHEETS] Ошибка подготовки листов: {e}")

    def _format_credits_sheet(self):
        """Применяет профессиональное форматирование к листу Кредиты и долги."""
        sheet_id = self._get_sheet_id(SHEET_CREDITS)
        if sheet_id is None:
            return

        requests = [
            # Синяя шапка с белым жирным текстом
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.18, "green": 0.34, "blue": 0.6},
                    "textFormat": {"bold": True, "fontSize": 10,
                                   "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP"
                }},
                "fields": "userEnteredFormat"
            }},
            # Закрепить первую строку
            {"updateSheetProperties": {
                "properties": {"sheetId": sheet_id,
                               "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount"
            }},
            # Строка Юрлица (КРИТИЧНО) — красный фон, строка 6 (индекс 5)
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 5, "endRowIndex": 6,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.87, "blue": 0.87},
                    "textFormat": {"bold": True}
                }},
                "fields": "userEnteredFormat"
            }},
            # Строка Анорбанк №2 (просрочка) — жёлтый фон, строка 3 (индекс 2)
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}
                }},
                "fields": "userEnteredFormat"
            }},
            # Лёгкий серый фон для Анорбанк №1
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.97}
                }},
                "fields": "userEnteredFormat"
            }},
            # Столбец A (Кредит) — широкий
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 210},
                "fields": "pixelSize"
            }},
            # Столбцы B–E
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 1, "endIndex": 5},
                "properties": {"pixelSize": 130},
                "fields": "pixelSize"
            }},
            # Столбцы F–J
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 5, "endIndex": 10},
                "properties": {"pixelSize": 115},
                "fields": "pixelSize"
            }},
            # Высота строки заголовка
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                           "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 42},
                "fields": "pixelSize"
            }},
            # Границы всей таблицы
            {"updateBorders": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 8,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "top": {"style": "SOLID", "width": 1,
                        "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
                "bottom": {"style": "SOLID", "width": 1,
                           "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
                "left": {"style": "SOLID", "width": 1,
                         "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
                "right": {"style": "SOLID", "width": 1,
                          "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
                "innerHorizontal": {"style": "SOLID", "width": 1,
                                    "color": {"red": 0.82, "green": 0.82, "blue": 0.82}},
                "innerVertical": {"style": "SOLID", "width": 1,
                                  "color": {"red": 0.82, "green": 0.82, "blue": 0.82}}
            }}
        ]

        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests}
            ).execute()
            print(f"[SHEETS] Форматирование листа '{SHEET_CREDITS}' применено")
        except Exception as e:
            print(f"[SHEETS] Ошибка форматирования: {e}")

    def _format_history_sheet(self):
        """Применяет форматирование к листу История."""
        sheet_id = self._get_sheet_id(SHEET_HISTORY)
        if sheet_id is None:
            return

        requests = [
            # Синяя шапка
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": 8},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.18, "green": 0.34, "blue": 0.6},
                    "textFormat": {"bold": True, "fontSize": 10,
                                   "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE"
                }},
                "fields": "userEnteredFormat"
            }},
            # Закрепить первую строку
            {"updateSheetProperties": {
                "properties": {"sheetId": sheet_id,
                               "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount"
            }},
            # Дата + Время — узкие
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": 2},
                "properties": {"pixelSize": 95},
                "fields": "pixelSize"
            }},
            # Кредит + Тип — средние
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 2, "endIndex": 4},
                "properties": {"pixelSize": 170},
                "fields": "pixelSize"
            }},
            # Сумма + Остаток + Комментарий + Статус
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 4, "endIndex": 8},
                "properties": {"pixelSize": 130},
                "fields": "pixelSize"
            }},
            # Высота заголовка
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                           "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 42},
                "fields": "pixelSize"
            }},
        ]

        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests}
            ).execute()
            print(f"[SHEETS] Форматирование листа '{SHEET_HISTORY}' применено")
        except Exception as e:
            print(f"[SHEETS] Ошибка форматирования История: {e}")

    def _init_credits_sheet(self):
        """Инициализирует лист Кредиты и долги с заголовками и данными."""
        if not self.service or not self.sheet_id:
            return

        try:
            headers = [[
                "Кредит / Долг", "Основной долг", "Остаток", "Ставка",
                "Ежемес. платёж", "Дата начала", "Дата конца",
                "Статус", "Просрочка", "Примечание"
            ]]
            credits = [
                ["Анорбанк №1", "50,000,000", "17,545,179", "42%", "2,537,983",
                 "01.03.2024", "04.02.2027", "активен", "нет", ""],
                ["Анорбанк №2", "25,100,000", "16,240,921", "47%", "1,329,616",
                 "21.10.2024", "14.10.2027", "активен", "1,317,952 сум", "просрочка"],
                ["AVO карта", "лимит", "23,510,000", "45%+", "~2,000,000",
                 "-", "-", "активна", "нет", "весь лимит использован"],
                ["Узумбанк микрозайм", "25,000,000", "22,000,000", "44%", "переменный",
                 "-", "-", "активен", "900,000 сум", "блокирует доступ к лимиту"],
                ["Юрлица (государственный)", "100,000,000", "~95,000,000", "23%/34.5%",
                 "1,900,000→4,000,000", "05.01.2025", "05.12.2025→2027",
                 "активен", "5,600,000 сум (73 дня)", "🔴 КРИТИЧНО до 30.06.2026"],
                ["Pulinform (рассрочка)", "25,000,000", "22,200,000", "0%", "2,800,000",
                 "00.00.2026", "10.07.2026+", "активна", "нет", "беспроцентная"]
            ]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_CREDITS}!A1",
                valueInputOption="RAW",
                body={"values": headers + credits}
            ).execute()
            print(f"[SHEETS] Лист '{SHEET_CREDITS}' инициализирован")
        except Exception as e:
            print(f"[SHEETS] Ошибка инициализации листа {SHEET_CREDITS}: {e}")

    def _init_history_sheet(self):
        """Инициализирует лист История с заголовками."""
        if not self.service or not self.sheet_id:
            return

        try:
            headers = [["Дата", "Время", "Кредит / Долг", "Тип",
                        "Сумма (сум)", "Остаток", "Комментарий", "Статус"]]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_HISTORY}!A1",
                valueInputOption="RAW",
                body={"values": headers}
            ).execute()
            print(f"[SHEETS] Лист '{SHEET_HISTORY}' инициализирован")
        except Exception as e:
            print(f"[SHEETS] Ошибка инициализации листа История: {e}")

    def add_payment(self, credit_name: str, payment_type: str, amount: float,
                    new_balance: Optional[float] = None, comment: str = ""):
        """Добавляет запись о платеже в лист История."""
        if not self.service or not self.sheet_id:
            return

        try:
            now = datetime.now()
            row = [
                now.strftime("%d.%m.%Y"),
                now.strftime("%H:%M"),
                credit_name,
                payment_type,
                f"{amount:,.0f}",
                f"{new_balance:,.0f}" if new_balance else "—",
                comment,
                "✅"
            ]
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_HISTORY}!A2",
                valueInputOption="RAW",
                body={"values": [row]}
            ).execute()
            print(f"[SHEETS] Запись: {credit_name} {amount:,.0f} сум")
        except Exception as e:
            print(f"[SHEETS] Ошибка добавления платежа: {e}")

    def update_credit_balance(self, credit_name: str, new_balance: float):
        """Обновляет остаток по кредиту в листе Кредиты и долги."""
        if not self.service or not self.sheet_id:
            return

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_CREDITS}!A:A"
            ).execute()
            rows = result.get("values", [])
            row_index = None
            for i, row in enumerate(rows):
                if row and row[0] == credit_name:
                    row_index = i + 1  # Google Sheets: 1-indexed
                    break
            if row_index:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=f"{SHEET_CREDITS}!C{row_index}",
                    valueInputOption="RAW",
                    body={"values": [[f"{new_balance:,.0f}"]]}
                ).execute()
                print(f"[SHEETS] Обновлен остаток {credit_name}: {new_balance:,.0f}")
        except Exception as e:
            print(f"[SHEETS] Ошибка обновления баланса: {e}")

    def get_credit_balance(self, credit_name: str) -> Optional[float]:
        """Получает текущий остаток по кредиту."""
        if not self.service or not self.sheet_id:
            return None

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{SHEET_CREDITS}!A:C"
            ).execute()
            rows = result.get("values", [])
            for row in rows:
                if row and len(row) >= 3 and row[0] == credit_name:
                    try:
                        return float(row[2].replace(",", ""))
                    except ValueError:
                        return None
            return None
        except Exception as e:
            print(f"[SHEETS] Ошибка получения баланса: {e}")
            return None


# ──────────────────────────────────────────────────
# Глобальный экземпляр
# ──────────────────────────────────────────────────
sheets_manager = SheetsManager()


def init_sheets():
    """Инициализирует Google Sheets при старте бота."""
    global sheets_manager
    if sheets_manager.service:
        sheets_manager._ensure_sheets()
        sheets_manager._init_credits_sheet()
        sheets_manager._init_history_sheet()
        sheets_manager._format_credits_sheet()
        sheets_manager._format_history_sheet()
        print("[SHEETS] Полностью инициализирована")
    else:
        print("[SHEETS] Сервис недоступен — функция отключена")


def log_payment(credit_name: str, amount: float, comment: str = "",
                new_balance: Optional[float] = None):
    """Логирует платёж в Google Sheets."""
    if sheets_manager.service:
        sheets_manager.add_payment(
            credit_name=credit_name,
            payment_type="оплата",
            amount=amount,
            new_balance=new_balance,
            comment=comment
        )


def log_early_repayment(credit_name: str, amount: float, comment: str = ""):
    """Логирует досрочное погашение."""
    if sheets_manager.service:
        sheets_manager.add_payment(
            credit_name=credit_name,
            payment_type="досрочное погашение",
            amount=amount,
            comment=comment
        )
