import asyncio
import logging
from typing import List, Dict, Optional
from aiogram.client.session import aiohttp

from seatable_api_menu import get_base_token, fetch_table

logger = logging.getLogger(__name__)


async def save_form_answers(form_data: Dict) -> bool:
    """Сохраняет ответы формы в указанную таблицу Seatable, используя только table_id (tid)"""
    logger.info("Начало сохранения ответов формы")

    # Проверяем обязательные поля
    required_fields = ['user_id', 'questions', 'answers', 'answers_table']
    if any(field not in form_data for field in required_fields):
        logger.error(f"Отсутствуют обязательные поля: {[f for f in required_fields if f not in form_data]}")
        return False

    if len(form_data['questions']) != len(form_data['answers']):
        logger.error(f"Количество вопросов ({len(form_data['questions'])}) != ответов ({len(form_data['answers'])})")
        return False

    # Получаем токен доступа
    token_data = await get_base_token()
    if not token_data:
        logger.error("Не удалось получить токен SeaTable")
        return False

    # Извлекаем table_id из URL
    try:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(form_data['answers_table'])
        query_params = parse_qs(parsed_url.query)
        table_id = query_params.get('tid', ['0000'])[0]
        logger.info(f"Table ID: {table_id}")
    except Exception as e:
        logger.error(f"Ошибка парсинга URL таблицы: {e}")
        return False

    # Подготавливаем данные
    user_id = str(form_data['user_id'])
    questions = form_data['questions']
    answers = form_data['answers']

    try:
        from datetime import datetime
        timestamp = form_data.get('timestamp', datetime.now().isoformat())
        formatted_date = datetime.fromisoformat(timestamp).strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logger.error(f"Ошибка форматирования даты: {e}")
        formatted_date = timestamp

    # Формируем строку для записи
    row_data = {
        'Name': user_id,
        'Дата и время': formatted_date
    }

    # Добавляем вопросы и ответы
    for question_data, answer in zip(questions, answers):
        question_text = question_data.get('Name', '')
        if question_text:
            row_data[question_text] = str(answer) if answer is not None else ''

    logger.info(f"Данные для записи: {row_data}")

    # 1. Сначала создаем недостающие колонки
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
                        "table_id": table_id,  # Используем только table_id
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

    # 2. Добавляем строку с данными
    rows_url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"
    payload = {
        "table_id": table_id,  # Используем только table_id
        "rows": [row_data]
    }

    try:
        logger.info(f"Отправка данных в таблицу {table_id}...")
        async with aiohttp.ClientSession() as session:
            async with session.post(rows_url, json=payload, headers=headers) as response:
                if response.status in (200, 201):
                    result = await response.json()
                    logger.info(f"Данные успешно сохранены. Ответ API: {result}")
                    return True

                error = await response.text()
                logger.error(f"Ошибка API: {response.status} - {error}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        return False


async def debug_table_info(table_id: str):
    token_data = await get_base_token()
    if not token_data:
        print("Не удалось получить токен")
        return

    # 1. Проверяем метаданные таблицы
    metadata_url = f"{token_data['dtable_server']}/api/v1/dtables/{token_data['dtable_uuid']}/metadata/"
    headers = {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        # Получаем метаданные
        async with session.get(metadata_url, headers=headers) as response:
            if response.status == 200:
                metadata = await response.json()
                print("Метаданные таблиц:")
                for table in metadata.get('tables', []):
                    if table.get('_id') == table_id:
                        print(f"Найдена таблица: {table}")
                        break
                else:
                    print(f"Таблица с id {table_id} не найдена")
            else:
                error = await response.text()
                print(f"Ошибка получения метаданных: {error}")

        # Получаем строки таблицы
        rows_url = f"{token_data['dtable_server']}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"
        params = {"table_id": table_id}
        async with session.get(rows_url, headers=headers, params=params) as response:
            if response.status == 200:
                rows = await response.json()
                print(f"Строки в таблице ({len(rows.get('rows', []))}):")
                for row in rows.get('rows', [])[:5]:  # Первые 5 строк
                    print(row)
            else:
                error = await response.text()
                print(f"Ошибка получения строк: {error}")


# Запуск для тестирования
# import asyncio
#
# asyncio.run(debug_table_info("K0Xd"))




# async def save_form_answers(form_data: Dict) -> bool:
#     """
#     Сохраняет ответы формы в указанную таблицу Seatable.
#     Возвращает True при успешном сохранении, False при ошибке.
#     """
#     logger.info(f"Начало сохранения ответов формы. Полученные данные: {form_data}")
#
#     # Проверяем наличие всех необходимых данных
#     if 'questions' not in form_data or 'answers' not in form_data:
#         logger.error("Отсутствуют questions или answers в form_data")
#         return False
#
#     if len(form_data['questions']) != len(form_data['answers']):
#         logger.error(
#             f"Количество вопросов ({len(form_data['questions'])}) не совпадает с количеством ответов ({len(form_data['answers'])})")
#         return False
#
#     token_data = await get_base_token()
#     if not token_data:
#         logger.error("Не удалось получить токен SeaTable")
#         return False
#
#     # Извлекаем table_id из URL (tid параметр)
#     answers_table_url = form_data.get('answers_table')
#     if not answers_table_url:
#         logger.error("Не указан URL таблицы для ответов")
#         return False
#
#     # Парсим table_id из URL
#     try:
#         from urllib.parse import urlparse, parse_qs
#         parsed_url = urlparse(answers_table_url)
#         query_params = parse_qs(parsed_url.query)
#         table_id = query_params.get('tid', ['0000'])[0]
#         logger.info(f"Извлеченный table_id: {table_id}")
#     except Exception as e:
#         logger.error(f"Ошибка парсинга URL таблицы: {e}")
#         return False
#
#     # Используем правильный user_id из form_data
#     user_id = str(form_data.get('user_id', ''))
#     if not user_id:
#         logger.error("Не указан user_id")
#         return False
#
#     answers = form_data['answers']
#     questions_data = form_data['questions']
#     logger.info(f"Обрабатываем ответы для user_id={user_id}, количество ответов: {len(answers)}")
#
#     # Собираем пары вопрос-ответ
#     qa_pairs = []
#     for i, (question_data, answer) in enumerate(zip(questions_data, answers), 1):
#         question_text = question_data.get('Name', f'Вопрос {i}')
#         qa_pairs.append({
#             'question': question_text,
#             'answer': str(answer) if answer is not None else ''
#         })
#         logger.debug(f"Вопрос {i}: '{question_text}', ответ: '{answer}'")
#
#     # Генерируем timestamp, если его нет в form_data
#     if 'timestamp' not in form_data:
#         from datetime import datetime
#         timestamp = datetime.now().isoformat()
#         logger.info(f"Сгенерирован новый timestamp: {timestamp}")
#     else:
#         timestamp = form_data['timestamp']
#         logger.info(f"Используем существующий timestamp: {timestamp}")
#
#     # Преобразуем timestamp в читаемый формат (14.08.2025 13:00)
#     try:
#         from datetime import datetime
#         dt = datetime.fromisoformat(timestamp)
#         formatted_date = dt.strftime("%d.%m.%Y %H:%M")
#         logger.info(f"Форматированная дата: {formatted_date}")
#     except Exception as e:
#         logger.error(f"Ошибка форматирования даты: {e}")
#         formatted_date = timestamp
#
#     # Подготавливаем данные для записи строки
#     row_data = {
#         'Name': user_id,  # Используем user_id из form_data
#         'Дата и время': formatted_date
#     }
#
#     for qa in qa_pairs:
#         row_data[qa['question']] = qa['answer']
#
#     logger.info(f"Данные для записи строки: {row_data}")
#
#     # Добавляем строку в таблицу через API
#     append_rows_url = f"{token_data['dtable_server'].rstrip('/')}/api/v1/dtables/{token_data['dtable_uuid']}/rows/"
#
#     headers = {
#         "Authorization": f"Bearer {token_data['access_token']}",
#         "Accept": "application/json",
#         "Content-Type": "application/json"
#     }
#
#     payload = {
#         "table_id": table_id,  # Используем table_id вместо table_name
#         "rows": [row_data]
#     }
#
#     try:
#         logger.info("Пытаемся добавить строку в таблицу...")
#         async with aiohttp.ClientSession() as session:
#             async with session.post(append_rows_url, json=payload, headers=headers) as response:
#                 if response.status in (200, 201):
#                     response_data = await response.json()
#                     logger.info(f"Ответы пользователя {user_id} успешно сохранены. Ответ сервера: {response_data}")
#                     return True
#
#                 error = await response.text()
#                 logger.error(f"Ошибка сохранения ответов. Статус: {response.status}, ошибка: {error}")
#
#                 # Дополнительная диагностика для ошибки 400
#                 if response.status == 400:
#                     logger.error(f"Детали запроса: URL: {append_rows_url}, Payload: {payload}")
#
#                 return False
#     except Exception as e:
#         logger.error(f"Ошибка при сохранении ответов: {e}")
#         return False