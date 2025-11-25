import pprint
import logging

from aiogram import types
from aiogram.types import ReplyKeyboardRemove

from app.services.cache import check_user_cache, RESTRICTING_MESSAGE

logger = logging.getLogger(__name__)


async def check_access (message: types.Message = None, callback_query: types.CallbackQuery = None) -> bool:
    """Функция отвечает, если ли доступ у пользователя. Если нет, выводит сообщение"""
    if callback_query:
        if not await check_user_cache(callback_query.from_user.id):
            await callback_query.answer(
                RESTRICTING_MESSAGE,
                show_alert=True
            )
            logger.info(f"У пользователя {callback_query.from_user.id} больше нет доступа.")
            return False
        else:
            logger.info(f"Доступ пользователя {callback_query.from_user.id} подтвержден")
            return True
    elif message:
        if not await check_user_cache(message.chat.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.chat.id} больше нет доступа.")
            return False
        else:
            logger.info(f"Доступ пользователя {message.chat.id} подтвержден")
            return True
    else:
        False
