import logging
import aiohttp

from config import Config
from app.seatable_api.api_base import get_base_token, fetch_table
from app.services.utils import normalize_phone

logger = logging.getLogger(__name__)

async def check_id_messenger(id_messenger: str) -> bool:
    """
    Функция для регистрации и получения доступа, а также для переподтверждения прав доступа и записи в кеш.
    Проверяет наличие ID_messenger в базе пользователей в таблице Роли и доступы.
    Возвращает True если пользователь найден, False если нет.
    """
    try:
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
                    [{'FIO': 'kit_company_account',
                      'ID_messenger': 'ХХХХХХХХХХХ',
                      'Phone': '+7ХХХХХХХХХХ',
                      'Role': 'newcomer',
                      '_ctime': '2025-11-24T08:13:29.157+00:00',
                      '_id': 'VbPzvSVARc6Gff-qO_C8LA',
                      '_mtime': '2025-11-25T07:08:27.303+00:00',
                      'Админы': ['WEkWAuJ5StKe-kaNf4cnMA']},
                """

                # Ищем пользователя с совпадающим id_messenger
                for row in data.get("rows", []):
                    if str(row.get("ID_messenger")) == str(id_messenger):
                        logger.info(f"Найден пользователь с ID_messenger: {id_messenger}")
                        return True

                logger.info(f"Пользователь с ID_messenger {id_messenger} не найден")
                return False

    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя: {str(e)}", exc_info=True)
        return False


async def register_id_messenger(phone: str, id_messenger: str) -> bool:
    """
    Функция для регистрации и получения доступа.
    Обращается по API к Seatable, ищет там пользователя по телефону и записывает его id_messenger.
    """
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

        # Используем человекочитаемые названия колонок, а не их внутренние ключи
        phone_column = "Phone"  # Колонка с телефонами
        id_messenger_column = "ID_messenger"  # Колонка для id_messenger

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
                        id_messenger_column: str(id_messenger)
                    }
                }

                # Отправка обновления
                async with session.put(base_url, headers=headers, json=update_data) as resp:
                    if resp.status != 200:
                        logger.error(f"Ошибка обновления: {resp.status} - {await resp.text()}")
                        return False

                    logger.info(f"ID_messenger успешно добавлен для пользователя с телефоном {phone}")
                    return True

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        return False

