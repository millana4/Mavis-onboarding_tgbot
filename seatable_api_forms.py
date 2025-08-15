import pprint
import logging
from typing import List, Dict, Optional
from aiogram.client.session import aiohttp

from seatable_api_menu import get_base_token

logger = logging.getLogger(__name__)


async def prepare_data_to_post_in_seatable(form_data: Dict) -> Optional[Dict]:
    """
    Подготавливает данные для сохранения в Seatable.
    Возвращает словарь с данными или None в случае ошибки.
    """
    # Проверяем обязательные поля
    required_fields = ['user_id', 'questions', 'answers', 'answers_table']
    if any(field not in form_data for field in required_fields):
        logger.error(f"Отсутствуют обязательные поля: {[f for f in required_fields if f not in form_data]}")
        return None

    if len(form_data['questions']) != len(form_data['answers']):
        logger.error(f"Количество вопросов ({len(form_data['questions'])}) != ответов ({len(form_data['answers'])})")
        return None

    # Извлекаем table_id из URL
    try:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(form_data['answers_table'])
        query_params = parse_qs(parsed_url.query)
        table_id = query_params.get('tid')[0]
        logger.info(f"Table ID: {table_id}")
    except Exception as e:
        logger.error(f"Ошибка парсинга URL таблицы: {e}")
        return None

    # Подготавливаем данные
    try:
        from datetime import datetime
        timestamp = form_data.get('timestamp', datetime.now().isoformat())
        formatted_date = datetime.fromisoformat(timestamp).strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logger.error(f"Ошибка форматирования даты: {e}")
        formatted_date = timestamp

    # Формируем строку для записи
    row_data = {
        'Name': str(form_data['user_id']),
        'Дата и время': formatted_date
    }

    # Добавляем вопросы и ответы
    for question_data, answer in zip(form_data['questions'], form_data['answers']):
        question_text = question_data.get('Name', '')
        if question_text:
            row_data[question_text] = str(answer) if answer is not None else ''

    return {
        'row_data': row_data,
        'table_id': table_id
    }


async def save_form_answers(form_data: Dict) -> bool:
    """Сохраняет ответы формы в указанную таблицу Seatable"""
    logger.info("Начало сохранения ответов формы")

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
        logger.info(f"Отправка данных в таблицу {table_id}...")
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
