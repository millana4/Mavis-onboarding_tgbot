import logging

from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from config import Config
from utils import prepare_telegram_message, normalize_phone

from app.services.cache_access import check_user_access, RESTRICTING_MESSAGE
from app.services.fsm import state_manager, AppStates
from app.seatable_api.api_auth import register_id_messanger, check_id_messanger
from app.seatable_api.api_base import fetch_table
from telegram.keyboards import share_contact_kb
from telegram.handlers.handler_table import handle_table_menu, handle_content_button


# Создаем роутер
router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик нажатия кнопки Старт"""
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} нажал кнопку Старт")

    # Проверяем, есть ли пользователь с таким id_telegram
    already_member = await check_id_messanger(user_id)
    logger.info(f"Пользователь {user_id} авторизован: {already_member}")

    if already_member:
        # Если пользователь есть в таблице, инициализируем навигацию
        await start_navigation(message=message)
    else:
        # Иначе просим поделиться контактом
        await message.answer(
            RESTRICTING_MESSAGE,
            reply_markup=share_contact_kb,
        )


@router.message(F.contact)
async def handle_contact(message: types.Message):
    """Обработка контакта для авторизации"""
    contact = message.contact
    user_id = message.from_user.id

    normalized_phone = normalize_phone(contact.phone_number)
    logger.info(f"Пользователь {user_id} прислал номер: {contact.phone_number} (нормализован: {normalized_phone})")

    # Добавляем id_messanger пользователя в таблицу Seatable
    success = await register_id_messanger(normalized_phone, user_id)

    if success:
        await message.answer(
            "🎉 Вы успешно авторизовались! Что вас интересует?",
            reply_markup=ReplyKeyboardRemove()
        )
        # После успешной регистрации запускаем навигацию
        await start_navigation(message=message)
    else:
        await message.answer(
            "🚫 Ваш номер телефона не найден в системе. Чтобы получить доступ в бот, обратитесь, пожалуйста, к эйчар-менеджеру.",
            reply_markup=ReplyKeyboardRemove()
        )


async def start_navigation(message: types.Message):
    """Инициализирует FSM и показывает главное меню"""
    try:
        # Проверяем права доступа
        if not await check_user_access(message.chat.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.chat.id} больше нет доступа. Запрещено в start_navigation")
            return
        else:
            logger.info(f"Доступ пользователя {message.chat.id} подтвержден")

        # Инициализируем состояние навигации
        state = await state_manager.set_state(
            message.chat.id,
            AppStates.CURRENT_MENU,
            {
                'current_menu': Config.SEATABLE_MAIN_MENU_ID,
                'navigation_history': [Config.SEATABLE_MAIN_MENU_ID]
            }
        )

        # Получаем контент и клавиатуру для главного меню
        content, keyboard = await handle_table_menu(Config.SEATABLE_MAIN_MENU_ID, message=message, state=state)

        kwargs = {
            'reply_markup': keyboard,
            'parse_mode': 'HTML'
        }

        # Отправляем контент в чат в зависимости от типа
        if content.get('image_url'):
            await message.answer_photo(
                photo=content['image_url'],
                caption=content.get('text', ''),
                **kwargs
            )
        elif content.get('video_url'):
            await message.answer_video(
                video=content['video_url'],
                caption=content.get('text', ''),
                **kwargs
            )
        elif content.get('text'):
            await message.answer(
                text=content['text'],
                **kwargs
            )
        elif keyboard:
            # Если есть только кнопки, отправляем пустое сообщение с ними
            await message.answer(" ", **kwargs)
        else:
            # На случай, если меню пустое
            await message.answer("Главное меню", **kwargs)

    except Exception as e:
        logger.error(f"Error in start_navigation for user {message.from_user.id}: {str(e)}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка при загрузке меню. Попробуйте позже.")


# Хендлер кнопки "Назад"
@router.callback_query(lambda c: c.data == 'back')
async def process_back_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки 'Назад'"""
    try:
        user_id = callback_query.from_user.id

        # Проверяем права доступа
        if not await check_user_access(user_id):
            await callback_query.answer(
                RESTRICTING_MESSAGE,
                show_alert=True
            )
            logger.info(f"У пользователя {user_id} больше нет доступа. Запрещено в process_back_callback")
            return
        else:
            logger.info(f"Доступ пользователя {user_id} подтвержден")

        data = await state_manager.get_data(user_id)
        navigation_history = data.get('navigation_history', [])

        if len(navigation_history) <= 1:
            await callback_query.answer("Вы в главном меню")
            return

        # Получаем текущий контент (если мы на content)
        current_key = navigation_history[-1]
        button_content = None
        if current_key.startswith('content:'):
            _, current_table_id, current_row_id = current_key.split(':')
            current_table_data = await fetch_table(current_table_id)
            current_row = next((r for r in current_table_data if r['_id'] == current_row_id), None)
            if current_row and current_row.get('Button_content'):
                button_content = prepare_telegram_message(current_row['Button_content'])

        # Получаем предыдущий экран
        previous_key = navigation_history[-2]
        await state_manager.update_data(
            user_id,
            current_menu=previous_key,
            navigation_history=navigation_history[:-1]
        )

        # Удаляем текущее сообщение
        try:
            await callback_query.message.delete()
        except:
            pass

        # Если был контент - постим его Button_content перед возвратом
        if button_content:
            if button_content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=button_content['image_url'],
                    caption=button_content.get('text', ''),
                    parse_mode="HTML"
                )
            elif button_content.get('text'):
                await callback_query.message.answer(
                    text=button_content['text'],
                    parse_mode="HTML"
                )

        # Возвращаемся к предыдущему экрану
        if previous_key.startswith('content:'):
            _, table_id, row_id = previous_key.split(':')
            content, keyboard = await handle_content_button(table_id, row_id)

            caption = content.get('text', '')
            if content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                if caption:  # Отправляем только если есть текст
                    await callback_query.message.answer(
                        text=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                elif keyboard:  # Если нет текста, но есть клавиатура
                    await callback_query.message.answer(
                        text=' ',
                        reply_markup=keyboard
                    )
        else:
            content, keyboard = await handle_table_menu(previous_key)

            menu_text = content.get('text', '')
            if content and content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=menu_text if menu_text else ' ',  # Пробел если пусто
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                if menu_text:  # Отправляем только если есть текст
                    await callback_query.message.answer(
                        text=menu_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                elif keyboard:  # Если нет текста, но есть клавиатура
                    await callback_query.message.answer(
                        text=' ',
                        reply_markup=keyboard
                    )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Back error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка возврата", show_alert=True)
