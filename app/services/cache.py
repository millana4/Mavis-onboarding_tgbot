import logging
from cachetools import TTLCache

from app.seatable_api.api_auth import check_id_messenger

logger = logging.getLogger(__name__)

# Кэш для хранения статуса пользователей (1 час TTL, до 2000 пользователей)
user_access_cache = TTLCache(maxsize=2000, ttl=3600)

# Кэш для хранения ролей пользователей (1 час TTL)
user_role_cache = TTLCache(maxsize=2000, ttl=3600)

# Сообщение для пользователя, который потерял доступ из-за увольнения
RESTRICTING_MESSAGE = "🚫 Извините, у вас больше нет доступа. Чтобы вернуть доступ, обратитесь, пожалуйста, к администратору."


async def check_user_cache(user_id: int) -> bool:
    """
    Проверяет права доступа пользователя с использованием кэширования.
    Возвращает True если доступ разрешен, False если запрещен.
    """
    # Проверяем кэш доступа
    logger.info(f"Кеш доступа: {user_access_cache}")
    if user_id in user_access_cache:
        logger.info(f"Cache hit for user {user_id}, access: {user_access_cache[user_id]}")
        return user_access_cache[user_id]

    # Если нет в кэше - проверяем через API
    logger.info(f"Cache miss for user {user_id}, checking via API...")
    try:
        has_access, role = await check_id_messenger(str(user_id))

        logger.info(f"API check result - has_access: {has_access}, role: {role}")

        # Сохраняем доступ и роль в кешах
        user_access_cache[user_id] = has_access
        if has_access:
            user_role_cache[user_id] = role
            logger.info(f"Role cached for user {user_id}: {role}")
        else:
            logger.info(f"User {user_id} has no access, role not cached")

        logger.info(f"Final access result for user {user_id}: {has_access}")
        return has_access
    except Exception as e:
        logger.error(f"Error checking user access for {user_id}: {str(e)}")
        return False


async def get_user_role_from_cache(user_id: int) -> str:
    """
    Получает роль пользователя из кеша.
    Если роли нет в кеше, проверяет доступ и возвращает роль.
    """
    # Сначала проверяем кеш ролей
    if user_id in user_role_cache:
        logger.info(f"Role cache hit for user {user_id}: {user_role_cache[user_id]}")
        return user_role_cache[user_id]

    # Если роли нет в кеше, но есть в кеше доступа - значит пользователь есть, но роль не записана
    # Проверяем доступ (это обновит оба кеша)
    has_access = await check_user_cache(user_id)

    if has_access and user_id in user_role_cache:
        return user_role_cache[user_id]

    # Если пользователь не найден или роль не определена - возвращаем роль по умолчанию
    logger.info(f"Role not found in cache for user {user_id}, using default 'employee'")
    return "employee"


async def clear_user_role_cache(user_id: int):
    """Очищает кеш роли для пользователя"""
    if user_id in user_role_cache:
        del user_role_cache[user_id]
        logger.info(f"Role cache cleared for user {user_id}")


async def clear_user_access_cache(user_id: int):
    """Очищает кеш доступа для пользователя"""
    if user_id in user_access_cache:
        del user_access_cache[user_id]
        logger.info(f"Access cache cleared for user {user_id}")