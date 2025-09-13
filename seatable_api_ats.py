import pprint

import logging
from typing import List, Dict, Optional
from aiogram.types import message

from config import Config
from seatable_api_base import fetch_table

logger = logging.getLogger(__name__)

async def get_employees(search_query):
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
        employees_data = await fetch_table(Config.SEATABLE_EMPLOYEE_BOOK_ID, 'ATS')
        # pprint.pprint(employees_data)
        return employees_data
    except Exception as e:
        logger.error(f"API error in get_employees: {str(e)}", exc_info=True)
        await message.answer("Ошибка при обработке запроса")
        return None

