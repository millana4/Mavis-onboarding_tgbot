import logging
import aiohttp

from config import Config
from app.seatable_api.api_base import get_base_token
from app.services.utils import normalize_phone

logger = logging.getLogger(__name__)

async def check_id_messanger(id_messanger: str) -> bool:
    """
    Функция для регистрации и получения доступа, а также для переподтверждения прав доступа и записи в кеш.
    Проверяет наличие ID_messanger в таблице Users Seatable.
    Возвращает True если пользователь найден, False если нет.
    """
    try:
        token_data = await get_base_token()
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

        base_url = f"{token_data['dtable_server']}api/v1/dtables/{token_data['dtable_uuid']}/rows/"
        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        params = {"table_id": Config.SEATABLE_USERS_TABLE_ID}

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ошибка запроса: {response.status}. Ответ: {error_text}")
                    return False

                data = await response.json()
                """
                Пример data:
                {'rows': 
                    [
                        {'_id': 'HiQYOMv4SLSsSMF_EpGpOg', 
                        '_mtime': '2025-07-31T11:52:03.380+00:00', 
                        '_ctime': '2025-07-08T11:58:08.914+00:00', 
                        'Name': 'usertest01_seller', 
                        'phone': '+7981ХХХХХХХ', 
                        'mailboxes': ['Rp5djUppTcqM1LQO_3x_gg', 'FrwMkbJJSfejzUb7a6RdoQ']
                        },
                    ]
                """

                # Ищем пользователя с совпадающим id_messanger
                for row in data.get("rows", []):
                    if str(row.get("ID_messanger")) == str(id_messanger):
                        logger.info(f"Найден пользователь с ID_messanger: {id_messanger}")
                        return True

                logger.info(f"Пользователь с ID_messanger {id_messanger} не найден")
                return False

    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя: {str(e)}", exc_info=True)
        return False


async def register_id_messanger(phone: str, id_messanger: str) -> bool:
    """
    Функция для регистрации и получения доступа.
    Обращается по API к Seatable, ищет там пользователя по телефону и записывает его id_messanger.
    """
    try:
        # Получаем токен
        token_data = await get_base_token()
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

        base_url = f"{token_data['dtable_server']}api/v1/dtables/{token_data['dtable_uuid']}/rows/"
        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Используем человекочитаемые названия колонок, а не их внутренние ключи
        phone_column = "Phone"  # Колонка с телефонами
        id_messanger_column = "ID_messanger"  # Колонка для id_messanger

        # Получаем параметры
        params = {
            "table_id": Config.SEATABLE_USERS_TABLE_ID,
            "convert_keys": "false"
        }

        async with aiohttp.ClientSession() as session:
            # Запрашиваем все строки
            async with session.get(base_url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка получения данных: {resp.status}")
                    return False

                data = await resp.json()
                rows = data.get("rows", [])

                for row in rows[:5]:
                    raw_phone = str(row.get(phone_column, "N/A"))
                    logger.debug(f"- Исходный: '{raw_phone}' | Нормализованный: '{normalize_phone(raw_phone)}'")

                # Ищем точное совпадение
                matched_row = None
                for row in rows:
                    if phone_column in row:
                        # Нормализуем телефон из таблицы перед сравнением
                        row_phone_normalized = normalize_phone(str(row[phone_column]))
                        if row_phone_normalized == phone:
                            matched_row = row
                            break

                if not matched_row:
                    logger.error("Совпадений не найдено. Проверьте:")
                    logger.error(
                        f"- Номер {phone} в таблице: {[normalize_phone(str(r.get(phone_column, ''))) for r in rows if phone_column in r]}")
                    logger.error(f"- Колонка телефон: {phone_column}")
                    return False

                row_id = matched_row.get("_id")
                if not row_id:
                    logger.error("У строки нет ID")
                    return False

                logger.info(f"Найдена строка пользователя для обновления (ID: {row_id})")

                # Подготовка обновления
                update_data = {
                    "table_id": Config.SEATABLE_USERS_TABLE_ID,
                    "row_id": row_id,
                    "row": {
                        id_messanger_column: str(id_messanger)
                    }
                }

                # Отправка обновления
                async with session.put(base_url, headers=headers, json=update_data) as resp:
                    if resp.status != 200:
                        logger.error(f"Ошибка обновления: {resp.status} - {await resp.text()}")
                        return False

                    logger.info(f"ID_messanger успешно добавлен для пользователя с телефоном {phone}")
                    return True

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        return False