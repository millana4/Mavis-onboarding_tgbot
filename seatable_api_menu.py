import asyncio
import pprint
import time

import aiohttp
import logging
from typing import List, Dict, Optional

from seatable_api_base import get_base_token

logger = logging.getLogger(__name__)


async def fetch_table(table_id: str = '0000') -> List[Dict]:
    """
    Получает строки таблицы.
    Аргументом принимает '_id'. В http таблицы указан как tid.
    Если _id при вызове не указан, то выставляет _id главного меню — 0000.
    """
    token_data = await get_base_token()
    if not token_data:
        logger.error("Не удалось получить токен SeaTable")
        return []

    url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

    headers = {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Accept": "application/json"
    }

    params = {"table_id": table_id}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                logger.debug(f"Успешный запрос: {url} {params}")
                return data.get("rows", [])

            error_text = await response.text()
            logger.debug(f"Ошибка: {response.status} - {error_text}")

    logger.error(f"Все варианты не сработали для table_id: {table_id}")
    return []


async def get_metadata() -> Optional[Dict[str, str]]:
    """Функция для отладки АПИ. Возвращает метаданные всех таблиц."""
    token_data = await get_base_token()
    if not token_data:
        logger.error("Не удалось получить токен SeaTable")
        return None

    url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/metadata/"

    headers = {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Accept": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                metadata = await response.json()
                return metadata

    logger.error("Все варианты endpoints вернули ошибку")
    return None


# Отладочный скрипт для вывода ответов json по API SeaTable
# if __name__ == "__main__":
#     async def main():
#         print("БАЗОВЫЙ ТОКЕН")
#         token_data = await get_base_token("ATS")
#         pprint.pprint(token_data)
#
#         print("ТАБЛИЦА")
#         menu_rows = await fetch_table('Yve2')
#         pprint.pprint(menu_rows)
#
#         print("ДРУГАЯ ТАБЛИЦА")
#         menu_rows = await fetch_table('Wxfy')
#         pprint.pprint(menu_rows)
#
#         print("МЕТАДАННЫЕ ТАБЛИЦ")
#         metadata = await get_metadata()
#         pprint.pprint(metadata)
#
#     asyncio.run(main())