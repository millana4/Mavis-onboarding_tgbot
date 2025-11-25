import pprint
import logging
from typing import List, Dict

from config import Config
from app.seatable_api.api_base import fetch_table, get_metadata

logger = logging.getLogger(__name__)

async def get_employees() -> List[Dict]:
    """
    Обращается по АПИ в таблицу со справочником и возвращает json с данными сотрудников.
    Пример ответа:
    [
       {
        'Company': ['ООО «Компания»'],
        'Department': 'IT',
        'Email': 'employee@email.ru',
        'Location': 'office №1',
        'Name/Department': 'Константин',
        'Number': 111,
        'Photo': ['https://photo.jpg'],
        'Position': 'job_title',
        '_ctime': '2025-09-09T11:11:16.637+00:00',
        '_id': 'LuKPfQWmQcWSRj6RZV9Z5g',
        '_mtime': '2025-09-13T13:25:45.708+00:00'},
    ]
    """
    try:
        employees_data = await fetch_table(table_id=Config.SEATABLE_EMPLOYEE_BOOK_ID, app='USER')
        # pprint.pprint(employees_data)
        return employees_data
    except Exception as e:
        logger.error(f"API error in get_employees: {str(e)}", exc_info=True)
        return None


async def get_department_list() -> List[str]:
    """
    Обращается по АПИ в таблицу со справочником, получает метаданные таблицы.
    Затем из метаданных формирует список отделов (только названия).
    """
    try:
        ats_table_metadata = await get_metadata(app='USER')

        # Достаём список таблиц
        tables_list = ats_table_metadata.get('metadata', {}).get('tables', [])

        for table in tables_list:
            if table.get('_id') == Config.SEATABLE_EMPLOYEE_BOOK_ID:
                columns = table.get('columns', [])

                # Ищем колонку Department
                for column in columns:
                    if column.get('name') == 'Department':
                        options = column.get('data', {}).get('options', [])
                        # Берём только названия отделов
                        return [opt.get("name") for opt in options if isinstance(opt, dict)]
        return []

    except Exception as e:
        print(f"Ошибка при получении списка отделов: {e}")
        return []

