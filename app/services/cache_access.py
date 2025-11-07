import logging
from cachetools import TTLCache

from app.seatable_api.api_auth import check_id_messenger

logger = logging.getLogger(__name__)

# Кэш для хранения статуса пользователей (1 час TTL, до 2000 пользователей)
user_access_cache = TTLCache(maxsize=2000, ttl=3600)

# Сообщение для пользователя, который потерял доступ из-за увольнения
RESTRICTING_MESSAGE = "🚫 Извините, у вас больше нет доступа. Чтобы вернуть доступ, обратитесь, пожалуйста, к администратору."


async def check_user_cache(user_id: int) -> bool:
    """
    Проверяет права доступа пользователя с использованием кэширования.
    Возвращает True если доступ разрешен, False если запрещен.
    """
    # Проверяем кэш
    print(user_access_cache)
    if user_id in user_access_cache:
        logger.info(f"Cache hit for user {user_id}")
        return user_access_cache[user_id]

    # Если нет в кэше - проверяем через API
    logger.info(f"Cache miss for user {user_id}, checking via API...")
    try:
        has_access = await check_id_messenger(str(user_id))
        user_access_cache[user_id] = has_access
        return has_access
    except Exception as e:
        logger.error(f"Error checking user access for {user_id}: {str(e)}")
        return False