import logging
from typing import Optional

from aiogram.client.session import aiohttp

from app.seatable_api.api_base import fetch_table, get_base_token
from config import Config

logger = logging.getLogger(__name__)

async def get_role_from_st(user_id: str) -> Optional[str]:
    """Получает роль пользователя из Seatable"""
    try:
        # Получаем данные пользователя из таблицы
        users_data = await fetch_table(table_id=Config.SEATABLE_USERS_TABLE_ID, app='USER')

        logger.info(f"Ищем пользователя с ID_messenger: {user_id} в таблице доступов и ролей, чтобы определить роль")

        for i, user in enumerate(users_data):
            current_id = str(user.get('ID_messenger'))
            search_id = str(user_id)

            if current_id == search_id:
                role = user.get('Role')
                logger.info(f"Найдены пользователь {i}: {user.get('FIO')}, и его роль {role}")
                return role

        logger.warning(f"Пользователь {user_id} не найден в таблице")
        return None

    except Exception as e:
        logger.error(f"Ошибка получения роли для {user_id}: {str(e)}", exc_info=True)
        return None


async def change_user_role(user_id: int, new_role: str) -> bool:
    """Изменяет роль пользователя в таблице Seatable"""
    try:
        # Получаем токен
        token_data = await get_base_token(app='USER')
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

        base_url = f"{token_data['dtable_server']}api/v1/dtables/{token_data['dtable_uuid']}/rows/"
        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Получаем пользователя
        users = await fetch_table(table_id=Config.SEATABLE_USERS_TABLE_ID, app='USER')
        user_row = next((u for u in users if str(u.get('ID_messenger')) == str(user_id)), None)

        if not user_row:
            logger.error(f"User {user_id} not found")
            return False

        row_id = user_row.get('_id')
        if not row_id:
            logger.error("User row has no ID")
            return False

        # Обновляем роль
        update_data = {
            "table_id": Config.SEATABLE_USERS_TABLE_ID,
            "row_id": row_id,
            "row": {
                "Role": new_role
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(base_url, headers=headers, json=update_data) as resp:
                if resp.status == 200:
                    logger.info(f"Role changed to {new_role} for user {user_id}")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Error updating role: {error}")
                    return False

    except Exception as e:
        logger.error(f"Error changing role for {user_id}: {str(e)}", exc_info=True)
        return False