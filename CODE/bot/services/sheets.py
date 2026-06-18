"""
sheets.py — Интеграция с Google Sheets для ведения финансов
===========================================================

Две таблицы:
1. "Кредиты" — основные условия, остатки, ставки
2. "История" — каждый платёж с датой, суммой, комментарием

Бот автоматически обновляет таблицы при упоминании платежей.
"""

import os
import json
from datetime import datetime
from typing import Optional

try:
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import Request
    import googleapiclient.discovery
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    print("[SHEETS] google-auth-oauthlib не установлен")


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

    def _ensure_sheets(self):
        """Создаёт листы если их нет."""
        if not self.service or not self.sheet_id:
            return

        try:
            # Проверяем какие листы есть
            sheet_meta = self.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            sheet_names = [s["properties"]["title"] for s in sheet_meta.get("sheets", [])]

            # Создаём листы если их нет
            requests = []
            if "Кредиты" not in sheet_names:
                requests.append({
                    "addSheet": {
                        "properties": {"title": "Кредиты", "gridProperties": {"rowCount": 100}}
                    }
                })
            if "История" not in sheet_names:
                requests.append({
                    "addSheet": {
                        "properties": {"title": "История", "gridProperties": {"rowCount": 1000}}
                    }
                })

            if requests:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={"requests": requests}
                ).execute()
                print("[SHEETS] Листы созданы")
        except Exception as e:
            print(f"[SHEETS] Ошибка создания листов: {e}")

    def _get_sheet_id(self, sheet_name: str) -> Optional[int]:
        """Возвращает числовой sheetId по имени листа."""
        try:
            meta = self.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            for s in meta.get("sheets", []):
                if s["properties"]["title"] == sheet_name:
                    return s["properties"]["sheetId"]
        except Exception:
            pass
        return None

    def _format_credits_sheet(self):
        """Применяет профессиональное форматирование к листу Кредиты."""
        sheet_id = self._get_sheet_id("Кредиты")
        if sheet_id is None:
            return

        requests = [
            # Жирный заголовок + фон + белый текст
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.18, "green": 0.34, "blue": 0.6},
                    "textFormat": {"bold": True, "fontSize": 10,
                                   "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
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
            # Строка с КРИТИЧНО (строка 6, индекс 5) — красный фон
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 5, "endRowIndex": 6,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.87, "blue": 0.87},
                    "textFormat": {"bold": True}
                }},
                "fields": "userEnteredFormat"
            }},
            # Строка Анорбанк №2 (просрочка) — жёлтый фон
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}
                }},
                "fields": "userEnteredFormat"
            }},
            # Чередующийся фон остальных строк (светло-серый)
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}
                }},
                "fields": "userEnteredFormat"
            }},
            # Ширина столбцов: А (Кредит) — широкий
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 200},
                "fields": "pixelSize"
            }},
            # Столбцы B, C, D, E — средние
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 1, "endIndex": 5},
                "properties": {"pixelSize": 130},
                "fields": "pixelSize"
            }},
            # Столбцы F-J — меньше
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 5, "endIndex": 10},
                "properties": {"pixelSize": 120},
                "fields": "pixelSize"
            }},
            # Высота строки заголовка
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                           "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 40},
                "fields": "pixelSize"
            }},
            # Границы таблицы
            {"updateBorders": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 8,
                           "startColumnIndex": 0, "endColumnIndex": 10},
                "top": {"style": "SOLID", "width": 1,
                        "color": {"red": 0.7, "green": 0.7, "blue": 0.7}},
                "bottom": {"style": "SOLID", "width": 1,
                           "color": {"red": 0.7, "green": 0.7, "blue": 0.7}},
                "left": {"style": "SOLID", "width": 1,
                         "color": {"red": 0.7, "green": 0.7, "blue": 0.7}},
                "right": {"style": "SOLID", "width": 1,
                          "color": {"red": 0.7, "green": 0.7, "blue": 0.7}},
                "innerHorizontal": {"style": "SOLID", "width": 1,
                                    "color": {"red": 0.85, "green": 0.85, "blue": 0.85}},
                "innerVertical": {"style": "SOLID", "width": 1,
                                  "color": {"red": 0.85, "green": 0.85, "blue": 0.85}}
            }}
        ]

        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests}
            ).execute()
            print("[SHEETS] Форматирование листа 'Кредиты' применено")
        except Exception as e:
            print(f"[SHEETS] Ошибка форматирования: {e}")

    def _format_history_sheet(self):
        """Применяет форматирование к листу История."""
        sheet_id = self._get_sheet_id("История")
        if sheet_id is None:
            return

        requests = [
            # Жирный заголовок
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": 8},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.18, "green": 0.34, "blue": 0.6},
                    "textFormat": {"bold": True, "fontSize": 10,
                                   "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
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
            # Ширина столбцов
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": 2},
                "properties": {"pixelSize": 100},
                "fields": "pixelSize"
            }},
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 2, "endIndex": 4},
                "properties": {"pixelSize": 160},
                "fields": "pixelSize"
            }},
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 4, "endIndex": 8},
                "properties": {"pixelSize": 130},
                "fields": "pixelSize"
            }},
        ]

        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests}
            ).execute()
            print("[SHEETS] Форматирование листа 'История' применено")
        except Exception as e:
            print(f"[SHEETS] Ошибка форматирования История: {e}")

    def _init_credits_sheet(self):
        """Инициализирует лист \"Кредиты\" с заголовками и данными."""
        if not self.service or not self.sheet_id:
            return

        try:
            # Заголовки
            headers = [
                ["Кредит", "Основной долг", "Остаток", "Ставка", "Ежемес. платёж",
                 "Дата начала", "Дата конца", "Статус", "Просрочка", "Примечание"]
            ]

            # Данные кредитов
            credits = [
                ["Анорбанк №1", "50,000,000", "17,545,179", "42%", "2,537,983",
                 "01.03.2024", "04.02.2027", "активен", "нет", ""],
                ["Анорбанк №2", "25,100,000", "16,240,921", "47%", "1,329,616",
                 "21.10.2024", "14.10.2027", "активен", "1,317,952 сум", "просрочка"],
                ["AVO карта", "лимит", "23,510,000", "45%+", "~2,000,000",
                 "-", "-", "активна", "нет", "весь лимит использован"],
                ["Узумбанк микрозайм", "25,000,000", "22,000,000", "44%", "переменный",
                 "-", "-", "активен", "900,000 сум", "блокирует доступ к лимиту"],
                ["Юрлица (государственный)", "100,000,000", "~95,000,000", "23%/34.5%", "1,900,000→4,000,000",
                 "05.01.2025", "05.12.2025→2027", "активен", "5,600,000 сум (73 дня)", "🔴 КРИТИЧНО до 30.06.2026"],
                ["Pulinform (рассрочка)", "25,000,000", "22,200,000", "0%", "2,800,000",
                 "00.00.2026", "10.07.2026+", "активна", "нет", "беспроцентная"]
            ]

            # Пишем в таблицу
            body = {
                "values": headers + credits
            }
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range="Кредиты!A1",
                valueInputOption="RAW",
                body=body
            ).execute()
            print("[SHEETS] Лист 'Кредиты' инициализирован")
        except Exception as e:
            print(f"[SHEETS] Ошибка инициализации листа Кредиты: {e}")

    def _init_history_sheet(self):
        """Инициализирует лист \"История\" с заголовками."""
        if not self.service or not self.sheet_id:
            return

        try:
            headers = [
                ["Дата", "Время", "Кредит", "Тип", "Сумма (сум)", "Остаток", "Комментарий", "Статус"]
            ]
            body = {"values": headers}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range="История!A1",
                valueInputOption="RAW",
                body=body
            ).execute()
            print("[SHEETS] Лист 'История' инициализирован")
        except Exception as e:
            print(f"[SHEETS] Ошибка инициализации листа История: {e}")

    def add_payment(self, credit_name: str, payment_type: str, amount: float,
                   new_balance: Optional[float] = None, comment: str = ""):
        """Добавляет запись о платеже в лист История.

        Args:
            credit_name: Название кредита (например \"Анорбанк №1\")
            payment_type: Тип платежа (оплата/досрочное погашение/учёт просрочки)
            amount: Сумма платежа
            new_balance: Новый остаток по кредиту
            comment: Дополнительный комментарий
        """
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

            # Добавляем строку в конец
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range="История!A2",
                valueInputOption="RAW",
                body={"values": [row]}
            ).execute()
            print(f"[SHEETS] Добавлена запись: {credit_name} {amount} сум")
        except Exception as e:
            print(f"[SHEETS] Ошибка добавления платежа: {e}")

    def update_credit_balance(self, credit_name: str, new_balance: float):
        """Обновляет остаток по кредиту в листе Кредиты.

        Args:
            credit_name: Название кредита
            new_balance: Новый остаток
        """
        if not self.service or not self.sheet_id:
            return

        try:
            # Находим строку по названию кредита
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range="Кредиты!A:A"
            ).execute()

            rows = result.get("values", [])
            row_index = None
            for i, row in enumerate(rows):
                if row and row[0] == credit_name:
                    row_index = i + 1  # +1 для Google Sheets (1-indexed)
                    break

            if row_index:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=f"Кредиты!C{row_index}",
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
                range="Кредиты!A:C"
            ).execute()

            rows = result.get("values", [])
            for row in rows:
                if row and len(row) >= 3 and row[0] == credit_name:
                    try:
                        balance_str = row[2].replace(",", "")
                        return float(balance_str)
                    except ValueError:
                        return None
            return None
        except Exception as e:
            print(f"[SHEETS] Ошибка получения баланса: {e}")
            return None


# Глобальный экземпляр
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


def log_payment(credit_name: str, amount: float, comment: str = "", new_balance: Optional[float] = None):
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
