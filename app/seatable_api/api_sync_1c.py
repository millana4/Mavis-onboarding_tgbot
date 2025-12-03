import logging
import aiohttp
from typing import Dict, Optional

from app.seatable_api.api_base import get_base_token
from config import Config

logger = logging.getLogger(__name__)


async def create_user_in_table(user_data: Dict) -> bool:
    """
    Создает пользователя в таблице пользователей
    """
    try:
        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

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
                    logger.info(f"Пользователь создан: {user_data.get('FIO')}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка создания пользователя: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при создании пользователя: {str(e)}")
        return False


async def update_user_in_table(row_id: str, user_data: Dict) -> bool:
    """
    Обновляет существующего пользователя в таблице пользователей
    """
    try:
        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

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
                    logger.info(f"Пользователь обновлен: {user_data.get('FIO')}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка обновления пользователя: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {str(e)}")
        return False


async def mark_1c_user_as_processed(row_id: str) -> bool:
    """
    Помечает пользователя как обработанного в таблице 1С
    """
    try:
        if not row_id:
            logger.error("Нет row_id для отметки пользователя")
            return False

        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
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
            "row_id": row_id,
            "row": {
                "Processed": True
            }
        }

        # Обновляем запись
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"Пользователь помечен как обработанный: {row_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка отметки пользователя: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при отметке пользователя: {str(e)}")
        return False