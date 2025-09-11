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