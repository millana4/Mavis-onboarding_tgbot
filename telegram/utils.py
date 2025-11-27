import pprint
import logging

from aiogram import types
from aiogram.types import ReplyKeyboardRemove

from app.services.cache import check_user_cache, RESTRICTING_MESSAGE, get_user_role_from_cache
from app.services.fsm import state_manager

logger = logging.getLogger(__name__)


async def check_access(message: types.Message = None, callback_query: types.CallbackQuery = None) -> bool:
    """Функция отвечает, если ли доступ у пользователя. Если нет, выводит сообщение"""
    user_id = None

    if callback_query:
        user_id = callback_query.from_user.id
        if not await check_user_cache(user_id):
            await callback_query.answer(RESTRICTING_MESSAGE, show_alert=True)
            logger.info(f"У пользователя {user_id} больше нет доступа.")
            return False
        else:
            # Обновляем роль FSM из кеша
            current_role = await get_user_role_from_cache(user_id)
            previous_role = await state_manager.get_user_role(user_id)

            # Если роль изменилась - сбрасываем навигацию и отправляем в главное меню новой роли
            if previous_role and previous_role != current_role:
                logger.info(f"Роль изменилась: {previous_role} -> {current_role}, сбрасываем навигацию")
                await state_manager.clear(user_id)

                # Устанавливаем новую роль
                await state_manager.set_user_role(user_id, current_role)

                # Отправляем пользователя в главное меню новой роли
                from telegram.handlers.handler_base import start_navigation
                if callback_query.message:
                    await start_navigation(message=callback_query.message)
                return False  # Прерываем текущее действие

            await state_manager.set_user_role(user_id, current_role)
            logger.info(f"Доступ пользователя {user_id} подтвержден, роль в FSM обновлена: {current_role}")
            return True

    elif message:
        user_id = message.chat.id
        if not await check_user_cache(user_id):
            await message.answer(RESTRICTING_MESSAGE, reply_markup=ReplyKeyboardRemove())
            logger.info(f"У пользователя {user_id} больше нет доступа.")
            return False
        else:
            # Обновляем роль FSM из кеша
            current_role = await get_user_role_from_cache(user_id)
            previous_role = await state_manager.get_user_role(user_id)

            # Если роль изменилась - сбрасываем навигацию и отправляем в главное меню новой роли
            if previous_role and previous_role != current_role:
                logger.info(f"Роль изменилась: {previous_role} -> {current_role}, сбрасываем навигацию")
                await state_manager.clear(user_id)

                # Устанавливаем новую роль
                await state_manager.set_user_role(user_id, current_role)

                # Отправляем пользователя в главное меню новой роли
                from telegram.handlers.handler_base import start_navigation
                await start_navigation(message=message)
                return False  # Прерываем текущее действие

            await state_manager.set_user_role(user_id, current_role)
            logger.info(f"Доступ пользователя {user_id} подтвержден, роль обновлена: {current_role}")
            return True
    else:
        return False
