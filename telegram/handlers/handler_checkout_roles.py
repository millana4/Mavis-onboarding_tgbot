from aiogram import F, Router
from aiogram.types import Message
import logging

from app.seatable_api.api_users import change_user_role
from app.services.fsm import state_manager, AppStates
from app.services.cache import clear_user_role_cache, clear_user_access_cache

logger = logging.getLogger(__name__)

# Создаем роутер
router = Router()


@router.message(F.text == "/checkout_newcomer")
async def handle_checkout_newcomer(message: Message):
    """Переключает пользователя в режим новичка"""
    user_id = message.chat.id

    # Проверяем права админа
    from app.services.broadcast import is_user_admin
    if not await is_user_admin(user_id):
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    # Очищаем состояние FSM
    await state_manager.clear(user_id)

    # Очищаем кеши доступа и ролей
    await clear_user_role_cache(user_id)
    await clear_user_access_cache(user_id)

    # Меняем роль в Seatable
    success = await change_user_role(user_id, "newcomer")

    if success:
        # Устанавливаем новую роль
        await state_manager.set_user_role(user_id, "newcomer")

        # Получаем ID главного меню для новой роли
        main_menu_id = await state_manager.get_main_menu_id(user_id)

        # Инициализируем навигацию заново
        await state_manager.update_data(
            user_id,
            current_menu=main_menu_id,
            navigation_history=[],
            current_state=AppStates.CURRENT_MENU,
            user_role="newcomer"
        )

        # Получаем и показываем контент меню
        from telegram.handlers.handler_table import handle_table_menu
        content, keyboard = await handle_table_menu(main_menu_id, str(user_id), message=message)

        kwargs = {'reply_markup': keyboard, 'parse_mode': 'HTML'}
        if content.get('image_url'):
            await message.answer_photo(photo=content['image_url'], caption=content.get('text', ''), **kwargs)
        elif content.get('text'):
            await message.answer(text=content['text'], **kwargs)
        else:
            await message.answer("Режим новичка активирован", **kwargs)

        await message.answer("Вы переключены в режим новичка")
    else:
        await message.answer("Ошибка при смене роли на новичка")


@router.message(F.text == "/checkout_employee")
async def handle_checkout_employee(message: Message):
    """Переключает пользователя в режим действующего сотрудника"""
    user_id = message.chat.id

    # Проверяем права админа
    from app.services.broadcast import is_user_admin
    if not await is_user_admin(user_id):
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    # Очищаем состояние FSM
    await state_manager.clear(user_id)

    # Очищаем кеши доступа и ролей
    await clear_user_role_cache(user_id)
    await clear_user_access_cache(user_id)

    # Меняем роль в Seatable
    success = await change_user_role(user_id, "employee")

    if success:
        # Устанавливаем новую роль
        await state_manager.set_user_role(user_id, "employee")

        # Получаем ID главного меню для новой роли
        main_menu_id = await state_manager.get_main_menu_id(user_id)

        # Инициализируем навигацию с чистого листа
        await state_manager.update_data(
            user_id,
            current_menu=main_menu_id,
            navigation_history=[],
            current_state=AppStates.CURRENT_MENU,
            user_role="employee"
        )

        # Получаем и показываем контент меню
        from telegram.handlers.handler_table import handle_table_menu
        content, keyboard = await handle_table_menu(main_menu_id, str(user_id), message=message)

        kwargs = {'reply_markup': keyboard, 'parse_mode': 'HTML'}
        if content.get('image_url'):
            await message.answer_photo(photo=content['image_url'], caption=content.get('text', ''), **kwargs)
        elif content.get('text'):
            await message.answer(text=content['text'], **kwargs)
        else:
            await message.answer("Режим сотрудника активирован", **kwargs)

        await message.answer("Вы переключены в режим действующего сотрудника")
    else:
        await message.answer("Ошибка при смене роли на действующего сотрудника")


@router.message(F.text == "/support")
async def handle_support(message: Message):
    """Обрабатывает команду поддержки"""
    user_id = message.chat.id

    support_text = """
    <b>Поддержка</b>
Если у вас возникли проблемы с работой бота или есть вопросы, напишите администратору: @kit_it_company
    """

    await message.answer(support_text, parse_mode='HTML')