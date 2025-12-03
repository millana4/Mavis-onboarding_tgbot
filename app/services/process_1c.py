import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dateutil.relativedelta import relativedelta

from config import Config
from app.seatable_api.api_base import fetch_table
from app.seatable_api.api_sync_1c import (
    create_user_in_table,
    update_user_in_table,
    mark_1c_user_as_processed
)
from app.services.pulse_tasks import create_pulse_all_tasks

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


async def process_1c_user(user: User1C) -> bool:
    """
    Обрабатывает одного пользователя из 1С
    """
    try:
        # Проверяем, существует ли пользователь уже в таблице пользователей
        exists, row_id = await user_exists_in_users_table(user.snils)

        if exists:
            # Подготавливаем данные для обновления
            update_data = {}
            if user.fio:          # ФИО - обновляем из 1С
                update_data['FIO'] = user.fio

            if user.employment_date:  # Роль - проверяем и обновляем на основе даты устройства
                should_be_role = "newcomer" if user.is_newcomer else "employee"
                update_data['Role'] = should_be_role

            # Обновляем запись
            success = await update_user_in_table(row_id, update_data)
        else:
            # Создаем нового пользователя
            user_data = user.to_users_table_format()
            success = await create_user_in_table(user_data)

        # Если операция успешна - создаем пульс-опросы и помечаем как обработанного
        if success:
            # Создаем пульс-опросы если нужно
            if user.is_less_than_year:
                await _create_pulse_for_user(user)

            # Помечаем как обработанного в 1С
            if user.row_id:
                await mark_1c_user_as_processed(user.row_id)

            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Ошибка обработки пользователя {user.fio}: {str(e)}")
        return False


async def _create_pulse_for_user(user: User1C) -> bool:
    """
    Создает пульс-опросы для пользователя
    """
    # Конвертируем User1C в dict для передачи
    user_dict = {
        'FIO': user.fio,
        'Name': user.snils,
        'Phone_private': user.phone,
        'Email': user.email,
        'Department': user.department,
        'Position': user.position,
        'Main_company': user.main_company,
        'Companies': user.companies,
        'Data_employment': user.employment_date.isoformat() if user.employment_date else None
    }

    try:
        return await create_pulse_all_tasks(user_dict)
    except Exception as e:
        logger.error(f"Ошибка создания пульс-опросов для {user.fio}: {e}")
        return False