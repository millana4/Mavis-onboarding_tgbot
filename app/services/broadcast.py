import pprint
import re
import logging
import aiohttp
from typing import List, Dict, Tuple
from config import Config
from app.seatable_api.api_base import fetch_table
from telegram.utils import check_access
from telegram.content import prepare_telegram_message


logger = logging.getLogger(__name__)


async def is_user_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    try:
        # 1. Получаем таблицу админов
        admins = await fetch_table(table_id=Config.SEATABLE_ADMIN_TABLE_ID, app='USER')

        # 2. Ищем админа, у которого в ID_messenger есть ссылка на пользователя
        admin_user = None
        for admin in admins:
            admin_messenger_ids = admin.get('ID_messenger', [])
            if isinstance(admin_messenger_ids, list) and admin_messenger_ids:
                # ID_messenger содержит список ID пользователей из таблицы пользователей
                admin_user = admin
                break

        if not admin_user:
            logger.info(f"Admin not found for user {user_id}")
            return False

        # 3. Проверяем доступ админа
        if not admin_user.get('Access'):
            logger.info(f"Admin {admin_user.get('FIO')} has no access rights")
            return False

        # 4. Получаем таблицу пользователей
        users = await fetch_table(table_id=Config.SEATABLE_USERS_TABLE_ID, app='USER')

        # 5. Ищем пользователя по ID мессенджера
        target_user = next(
            (u for u in users if str(u.get('ID_messenger')) == str(user_id)),
            None
        )

        if not target_user:
            logger.info(f"User {user_id} not found in users table")
            return False

        # 6. Проверяем, что ID пользователя совпадает с ID из списка админа
        target_user_id = target_user.get('_id')
        admin_messenger_ids = admin_user.get('ID_messenger', [])

        is_admin = target_user_id in admin_messenger_ids

        logger.info(f"Admin check: user_id={user_id}, target_user_id={target_user_id}, "
                    f"admin_messenger_ids={admin_messenger_ids}, is_admin={is_admin}")

        return is_admin

    except Exception as e:
        logger.error(f"Error checking admin rights for {user_id}: {str(e)}", exc_info=True)
        return False


async def get_broadcast_notifications() -> List[Dict]:
    """Получает список уведомлений для рассылки"""
    return await fetch_table(table_id=Config.BROADCAST_TABLE_ID, app='HR')


async def get_active_users() -> List[Dict]:
    """Получает список активных пользователей"""
    users = await fetch_table(table_id=Config.SEATABLE_USERS_TABLE_ID, app='USER')
    return [user for user in users if user.get('ID_messenger')]


async def prepare_notification_content(notification: Dict) -> Tuple[Dict, bytes, str]:
    """
    Подготавливает контент уведомления для отправки
    Возвращает: (контент, файл_данные, имя_файла)
    """
    content = prepare_telegram_message(notification.get('Content', ''))

    file_data = None
    filename = None
    attachment = notification.get('Attachment')

    if attachment:
        file_data, filename = await download_file(attachment)

    return content, file_data, filename


async def download_file(file_url: str) -> Tuple[bytes, str]:
    """Скачивает файл и возвращает данные и имя файла"""
    try:
        # Добавляем параметр для скачивания файла
        if '?' not in file_url:
            download_url = file_url + '?dl=1'
        else:
            download_url = file_url + '&dl=1'

        async with aiohttp.ClientSession() as session:
            # Получаем название файла
            async with session.get(file_url) as html_response:
                html_content = await html_response.text()
                filename = extract_filename_from_html(html_content) or "file"

            # Скачиваем файл
            async with session.get(download_url) as file_response:
                file_response.raise_for_status()
                file_data = await file_response.read()

            return file_data, filename

    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {str(e)}")
        raise


def extract_filename_from_html(html_content: str) -> str:
    """Извлекает название файла из HTML Seafile"""
    try:
        # Ищем в og:title
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        if title_match:
            return title_match.group(1)

        # Ищем в og:description
        desc_match = re.search(r'<meta property="og:description" content="Share link for ([^"]+)"', html_content)
        if desc_match:
            return desc_match.group(1)

        return "file"

    except Exception as e:
        logger.error(f"Ошибка извлечения названия файла: {str(e)}")
        return "file"