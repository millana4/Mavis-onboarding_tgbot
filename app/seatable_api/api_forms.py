import pprint
import logging
import aiohttp
from typing import Dict

from app.seatable_api.api_base import get_base_token, fetch_table
from app.services.forms import prepare_data_to_post_in_seatable
from config import Config

logger = logging.getLogger(__name__)


async def save_form_answers(form_data: Dict) -> bool:
    """Сохраняет ответы формы в указанную таблицу Seatable"""
    logger.info("Начало сохранения ответов формы")

    # Получаем данные пользователя из таблицы
    users_data = await fetch_table(table_id=Config.SEATABLE_USERS_TABLE_ID, app='USER')

    # Добавляем данные пользователя в form_data
    for user in users_data:
        current_id = str(user.get('ID_messenger'))
        if current_id == str(form_data.get('user_id')):
            form_data['user_fio'] = user.get('FIO')
            form_data['user_phone'] = user.get('Phone')
            break

    # Получаем токен доступа
    token_data = await get_base_token()
    if not token_data:
        logger.error("Не удалось получить токен SeaTable")
        return False

    # Подготавливаем данные
    prepared_data = await prepare_data_to_post_in_seatable(form_data)
    if not prepared_data:
        logger.error("Не удалось подготовить данные для сохранения")
        return False

    row_data = prepared_data['row_data']
    table_id = prepared_data['table_id']

    logger.info(f"Данные для записи: {row_data}")

    # Сначала создаем недостающие колонки
    api_url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/columns/"
    headers = {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Получаем существующие колонки
    try:
        async with aiohttp.ClientSession() as session:
            # Проверяем существующие колонки
            params = {"table_id": table_id}
            async with session.get(api_url, headers=headers, params=params) as response:
                existing_columns = []
                if response.status == 200:
                    columns_data = await response.json()
                    existing_columns = [col['name'] for col in columns_data.get('columns', [])]
                    logger.info(f"Существующие колонки: {existing_columns}")
                else:
                    error = await response.text()
                    logger.warning(f"Не удалось получить колонки: {error}")

            # Создаем недостающие колонки
            for col_name in row_data.keys():
                if col_name not in existing_columns:
                    payload = {
                        "table_id": table_id,
                        "column_name": col_name,
                        "column_type": "text"
                    }
                    async with session.post(api_url, json=payload, headers=headers) as resp:
                        if resp.status not in (200, 201):
                            error = await resp.text()
                            logger.error(f"Ошибка создания колонки {col_name}: {error}")
                        else:
                            logger.info(f"Колонка «{col_name}» создана")
    except Exception as e:
        logger.error(f"Ошибка при работе с колонками: {e}")

    # Добавляем строку с данными
    rows_url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"

    # Формируем payload
    payload = {
        "table_id": table_id,
        "row": row_data
    }

    try:
        logger.info(f"Отправка данных в таблицу {table_id}")
        async with aiohttp.ClientSession() as session:
            async with session.post(rows_url, json=payload, headers=headers) as response:
                if response.status in (200, 201):
                    result = await response.json()
                    logger.info(f"Данные успешно сохранены. Ответ API: {result}")

                    # Дополнительная проверка - получаем добавленную строку
                    check_params = {"table_id": table_id}
                    async with session.get(rows_url, headers=headers, params=check_params) as check_resp:
                        if check_resp.status == 200:
                            check_data = await check_resp.json()
                            logger.info(f"Проверка: в таблице {len(check_data.get('rows', []))} строк")
                            logger.debug(
                                f"Последняя строка: {check_data.get('rows', [])[-1] if check_data.get('rows') else 'нет данных'}")
                        else:
                            error = await check_resp.text()
                            logger.warning(f"Ошибка проверки: {error}")

                    return True

                error = await response.text()
                logger.error(f"Ошибка API: {response.status} - {error}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        return False
