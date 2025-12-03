import logging
from datetime import datetime, date, timedelta
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dateutil.relativedelta import relativedelta

from config import Config
from app.seatable_api.api_base import fetch_table, get_base_token
import aiohttp

logger = logging.getLogger(__name__)


class User1C:
    """DTO для данных пользователя из 1С"""

    def __init__(self, row_data: Dict):
        self.snils = row_data.get('Name')  # СНИЛС
        self.fio = row_data.get('FIO')
        self.phone = row_data.get('Phone_private')
        self.email = row_data.get('Email')
        self.department = row_data.get('Department')
        self.position = row_data.get('Position')
        self.main_company = row_data.get('Main_company')
        self.companies = row_data.get('Companies', [])
        self.employment_date = self._parse_date(row_data.get('Data_employment'))
        self.processed = row_data.get('Processed', False)
        self.row_id = row_data.get('_id')

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Парсит дату из строки"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    @property
    def is_newcomer(self) -> bool:
        """Проверяет, работает ли меньше 3 месяцев"""
        if not self.employment_date:
            return False

        three_months_ago = datetime.now().date() - relativedelta(months=3)
        return self.employment_date > three_months_ago

    @property
    def is_less_than_year(self) -> bool:
        """Проверяет, работает ли меньше года"""
        if not self.employment_date:
            return False

        one_year_ago = datetime.now().date() - relativedelta(years=1)
        return self.employment_date > one_year_ago

    def to_users_table_format(self) -> Dict:
        """Конвертирует в формат таблицы пользователей"""
        role = "newcomer" if self.is_newcomer else "employee"

        return {
            'Name': self.snils,
            'FIO': self.fio,
            'Phone': self.phone,
            'Email': self.email,
            'Department': self.department,
            'Position': self.position,
            'Main_company': self.main_company,
            'Companies': self.companies,
            'Role': role,
            'ID_messenger': '',  # Пусто
            'Data_employment': self.employment_date.isoformat() if self.employment_date else None
        }


async def get_unprocessed_1c_users() -> List[User1C]:
    """
    Получает список необработанных пользователей из 1С
    """
    try:
        # Получаем данные из таблицы 1С
        rows = await fetch_table(
            table_id=Config.SEATABLE_1C_TABLE_ID,
            app='USER'
        )

        if not rows:
            return []

        # Фильтруем необработанных пользователей
        unprocessed_users = []
        for row in rows:
            user = User1C(row)

            # Пропускаем пользователей без СНИЛС или ФИО
            if not user.snils or not user.fio:
                continue

            # Проверяем, обработан ли пользователь
            if not user.processed:
                unprocessed_users.append(user)

        return unprocessed_users

    except Exception as e:
        logger.error(f"Ошибка при получении пользователей из 1С: {str(e)}")
        return []


async def user_exists_in_users_table(snils: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, существует ли пользователь в таблице пользователей по СНИЛС
    """
    try:
        users = await fetch_table(
            table_id=Config.SEATABLE_USERS_TABLE_ID,
            app='USER'
        )

        for user in users:
            if user.get('Name') == snils:
                return True, user.get('_id')

        return False, None

    except Exception as e:
        logger.error(f"Ошибка при проверке существования пользователя {snils}: {str(e)}")
        return False, None


async def create_user_in_users_table(user: User1C) -> bool:
    """
    Создает пользователя в таблице пользователей
    """
    try:
        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            return False

        # Подготавливаем данные
        user_data = user.to_users_table_format()

        # URL для создания записи
        url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "table_id": Config.SEATABLE_USERS_TABLE_ID,
            "row": user_data
        }

        # Создаем запись
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status in (200, 201):
                    # Если сотрудник работает меньше года - создаем пульс-опросы
                    if user.is_less_than_year:
                        await create_pulse(user)

                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка создания пользователя {user.snils}: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при создании пользователя {user.snils}: {str(e)}")
        return False


async def update_user_in_users_table(user: User1C, row_id: str) -> bool:
    """
    Обновляет существующего пользователя в таблице пользователей
    """
    try:
        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            return False

        # Подготавливаем данные для обновления
        user_data = user.to_users_table_format()

        # Удаляем ID_messenger из обновления, если он пустой
        if not user_data.get('ID_messenger'):
            user_data.pop('ID_messenger', None)

        # URL для обновления записи
        url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "table_id": Config.SEATABLE_USERS_TABLE_ID,
            "row_id": row_id,
            "row": user_data
        }

        # Обновляем запись
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    # Если сотрудник работает меньше года - создаем пульс-опросы
                    if user.is_less_than_year:
                        await create_pulse(user)

                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка обновления пользователя {user.snils}: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя {user.snils}: {str(e)}")
        return False


async def mark_user_as_processed(user: User1C) -> bool:
    """
    Помечает пользователя как обработанного в таблице 1С
    """
    try:
        if not user.row_id:
            return False

        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            return False

        # URL для обновления записи
        url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "table_id": Config.SEATABLE_1C_TABLE_ID,
            "row_id": user.row_id,
            "row": {
                "Processed": True
            }
        }

        # Обновляем запись
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка отметки пользователя {user.snils}: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при отметке пользователя {user.snils}: {str(e)}")
        return False


async def create_pulse(user: User1C):
    pass