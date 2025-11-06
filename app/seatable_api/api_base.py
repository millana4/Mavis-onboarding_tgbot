import asyncio
import pprint
import time
import aiohttp
import logging
from typing import List, Dict, Optional

from config import Config

logger = logging.getLogger(__name__)

# Глобальный кэш токена основного приложения
_token_app_cache: Dict[str, Optional[Dict]] = {
    "token_data": None,
    "timestamp": 0
}

# Глобальный кэш токена телефонного справочника
_token_ats_cache: Dict[str, Optional[Dict]] = {
    "token_data": None,
    "timestamp": 0
}

_TOKEN_TTL = 172800  # время жизни токена в секундах — 48 часов


async def get_base_token(app='HR') -> Optional[Dict]:
    """
    Получает временный токен для синхронизации по Апи.

    На вход нужно передать:
    - Если нужен токен для телефонного справочника, передать 'ATS'.
    - Если нужен токен для основного приложения, то либо передать 'HR', либо ничего не передавать.

    Возвращает словарь:
    {'access_token': 'token_string',
    'app_name': 'mavis-onboarding',
    'dtable_db': 'https://server_name/dtable-db/',
    'dtable_name': 'Mavis_onboarding',
    'dtable_server': 'https://server_name/dtable-server/',
    'dtable_socket': 'https://server_name/',
    'dtable_uuid': '5ce74477-6800-492d-b92e-00d9cd0589a6',
    'workspace_id': 11}
    """

    # Запрашиваем из кеша токен для основного приложения HR или для телефонного справочника —
    # в зависимости от того, что передано на вход
    now = time.time()

    if app == 'ATS':
        cached = _token_ats_cache["token_data"]
        cached_time = _token_ats_cache["timestamp"]
    else:
        cached = _token_app_cache["token_data"]
        cached_time = _token_app_cache["timestamp"]

    if cached and (now - cached_time) < _TOKEN_TTL:
        return cached

    # URL одинаковый для обоих приложений
    url = f"{Config.SEATABLE_SERVER}/api/v2.1/dtable/app-access-token/"

    # В заголовок передаем ключ API для основного приложения HR или для телефонного справочника
    if app == 'ATS':
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {Config.SEATABLE_API_ATS_TOKEN}"
        }
    else:
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {Config.SEATABLE_API_APP_TOKEN}"
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                token_data = await response.json()
                logger.debug("Base token successfully obtained and cached")

                # Обновляем кэш
                if app == 'ATS':
                    _token_ats_cache["token_data"] = token_data
                    _token_ats_cache["timestamp"] = now
                else:
                    _token_app_cache["token_data"] = token_data
                    _token_app_cache["timestamp"] = now

                return token_data

    except aiohttp.ClientError as e:
        logger.error(f"API request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

    return None


async def fetch_table(table_id: str = '0000', app: str = "HR") -> List[Dict]:
    """
    Получает строки таблицы.
    Аргументом принимает '_id'. В http таблицы указан как tid.
    Если _id при вызове не указан, то выставляет _id главного меню — 0000.
    """
    # Запрашиваем токен для нужного приложения — Мавис-HR или телефонный справочник
    if app == 'ATS':
        token_data = await get_base_token('ATS')
    else:
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


async def get_metadata(app: str = "HR") -> Optional[Dict[str, str]]:
    """Функция возвращает метаданные любой таблицы."""
    # Запрашиваем токен для нужного приложения — Мавис-HR или телефонный справочник
    if app == 'ATS':
        token_data = await get_base_token('ATS')
    else:
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
#         menu_rows = await fetch_table('0000')
#         pprint.pprint(menu_rows)
#
#         print("ДРУГАЯ ТАБЛИЦА")
#         menu_rows = await fetch_table('Wxfy')
#         pprint.pprint(menu_rows)
#
#         print("МЕТАДАННЫЕ ТАБЛИЦ")
#         metadata = await get_metadata('ATS')
#         pprint.pprint(metadata)
#
#     asyncio.run(main())