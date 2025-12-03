import logging
import aiohttp
from typing import Dict, Optional

from app.seatable_api.api_base import get_base_token
from config import Config

logger = logging.getLogger(__name__)


async def create_pulse_task(task_data: Dict) -> bool:
    """
    Создает задачу пульс-опроса в таблице SeaTable
    """
    try:
        # Получаем токен для базы пульс-опросов
        token_data = await get_base_token(app='PULSE')
        if not token_data:
            logger.error("Не удалось получить токен для базы пульс-опросов")
            return False

        # URL для записи
        url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "table_id": Config.SEATABLE_PULSE_TASKS_ID,
            "row": task_data
        }

        # Отправляем запрос
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status in (200, 201):
                    logger.info(f"Задача на пульс-опрос создана: {task_data.get('FIO')} - {task_data.get('Type')}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка создания задачи: {response.status} - {error_text}")
                    return False

    except Exception as e:
        logger.error(f"Ошибка при сохранении задачи: {e}")
        return False


async def get_pulse_tasks() -> Optional[list]:
    """
    Получает список задач пульс-опросов
    """
    try:
        token_data = await get_base_token(app='PULSE')
        if not token_data:
            return None

        url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json"
        }

        params = {"table_id": Config.SEATABLE_PULSE_TASKS_ID}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("rows", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка получения задач: {response.status} - {error_text}")
                    return None

    except Exception as e:
        logger.error(f"Ошибка при получении задач: {e}")
        return None


async def task_exists(snils: str, poll_type: str) -> bool:
    """
    Проверяет, существует ли уже задача для данного пользователя и типа опроса
    """
    try:
        tasks = await get_pulse_tasks()
        if not tasks:
            return False

        for task in tasks:
            if task.get('Name') == snils and task.get('Type') == poll_type:
                logger.info(f"Задача уже существует: {snils} - {poll_type}")
                return True

        return False

    except Exception as e:
        logger.error(f"Ошибка проверки существования задачи: {e}")
        return False