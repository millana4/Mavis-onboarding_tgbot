import logging
from cachetools import TTLCache
from aiogram import types

from app.seatable_api.api_auth import check_id_messanger

logger = logging.getLogger(__name__)

# Кэш для хранения статуса пользователей (1 час TTL, до 2000 пользователей)
user_access_cache = TTLCache(maxsize=2000, ttl=3600)

# Сообщение для пользователя, который потерял доступ из-за увольнения
RESTRICTING_MESSAGE = "🚫 Извините, у вас больше нет доступа. Чтобы вернуть доступ, обратитесь, пожалуйста, к администратору."


async def check_user_access(user_id: int) -> bool:
    """
    Проверяет права доступа пользователя с использованием кэширования.
    Возвращает True если доступ разрешен, False если запрещен.
    """
    # Проверяем кэш
    if user_id in user_access_cache:
        logger.debug(f"Cache hit for user {user_id}")
        return user_access_cache[user_id]

    # Если нет в кэше - проверяем через API
    logger.debug(f"Cache miss for user {user_id}, checking via API...")
    try:
        has_access = await check_id_messanger(str(user_id))
        user_access_cache[user_id] = has_access
        return has_access
    except Exception as e:
        logger.error(f"Error checking user access for {user_id}: {str(e)}")
        return False


async def require_access_decorator(func):
    """
    Декоратор для проверки прав доступа перед выполнением функции.
    """

    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = message.from_user.id

        if not await check_user_access(user_id):
            await message.answer(
                "🚫 Извините, у вас больше нет доступа. Обратитесь, пожалуйста, к администратору системы.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return

        # Если доступ есть, выполняем оригинальную функцию
        return await func(message, *args, **kwargs)

    return wrapper

