from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from table_handlers import handle_table_menu, handle_content_button
from seatable_api import fetch_table
from utils import download_and_send_file
import logging

# Создаем роутер
router = Router()
logger = logging.getLogger(__name__)


class Navigation(StatesGroup):
    current_menu = State()  # Хранит текущее меню и историю для каждого пользователя

# Хендлер команды /start
@router.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    """Обработчик команды /start с инициализацией FSM"""
    try:
        # Инициализируем состояние навигации
        await state.update_data(
            current_menu=Config.SEATABLE_MAIN_MENU_ID,
            navigation_history=[Config.SEATABLE_MAIN_MENU_ID]
        )

        content, keyboard = await handle_table_menu(Config.SEATABLE_MAIN_MENU_ID)

        kwargs = {
            'reply_markup': keyboard,
            'parse_mode': 'HTML'
        }

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
            await message.answer(" ", **kwargs)

    except Exception as e:
        logger.error(f"Error in /start: {str(e)}", exc_info=True)
        await message.answer("Произошла ошибка, попробуйте позже")


# Хендлер для кнопок меню
@router.callback_query(lambda c: c.data.startswith('menu:'))
async def process_menu_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик навигации по меню с поддержкой истории"""
    try:
        # Получаем текущее состояние
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [Config.SEATABLE_MAIN_MENU_ID])

        # Получаем новый table_id
        new_table_id = callback_query.data.split(':')[1]

        # Обновляем историю
        navigation_history.append(new_table_id)
        await state.update_data(
            current_menu=new_table_id,
            navigation_history=navigation_history
        )

        logger.debug(f"Navigation history: {navigation_history}")

        # Получаем контент и клавиатуру
        content, keyboard = await handle_table_menu(new_table_id)

        if not keyboard:
            await callback_query.answer("Меню не найдено", show_alert=True)
            return

        # Обновляем сообщение
        if content.get('image_url'):
            await callback_query.message.edit_media(
                media=types.InputMediaPhoto(
                    media=content['image_url'],
                    caption=content.get('text', ''),
                    parse_mode="HTML"
                ),
                reply_markup=keyboard
            )
        elif content.get('text'):
            await callback_query.message.edit_text(
                text=content['text'],
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Menu navigation error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка навигации", show_alert=True)


@router.callback_query(lambda c: c.data.startswith('content:'))
async def process_content_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик нажатия на кнопки контента"""
    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {str(e)}")

    _, table_id, row_id = callback_query.data.split(':')
    user_id = callback_query.from_user.id
    logger.info(f"Обработка контента table_id={table_id}, row_id={row_id} для пользователя {user_id}")

    try:
        # Обновляем историю навигации
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [Config.SEATABLE_MAIN_MENU_ID])

        # Добавляем текущий контент в историю
        content_key = f"content:{table_id}:{row_id}"
        navigation_history.append(content_key)
        await state.update_data(
            current_menu=content_key,
            navigation_history=navigation_history
        )

        # Получаем данные строки
        table_data = await fetch_table(table_id)
        row = next((r for r in table_data if r['_id'] == row_id), None)

        # Обработка вложения, если оно есть
        if row and row.get('Attachment'):
            file_url = row['Attachment']
            logger.debug(f"Попытка скачать: {file_url}")
            await download_and_send_file(file_url=file_url, callback_query=callback_query)

        # Отправка основного контента
        content, keyboard = await handle_content_button(table_id, row_id)

        if content.get('image_url'):
            await callback_query.message.answer_photo(
                photo=content['image_url'],
                caption=content.get('text', ''),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback_query.message.answer(
                text=content['text'],
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Ошибка обработки контента: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка", show_alert=True)



# Хендлер кнопки "Назад"
@router.callback_query(lambda c: c.data == 'back')
async def process_back_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад' с поддержкой истории"""
    try:
        # Получаем текущее состояние
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [Config.SEATABLE_MAIN_MENU_ID])

        if len(navigation_history) <= 1:
            await callback_query.answer("Вы в главном меню")
            return

        # Удаляем текущее меню из истории
        navigation_history.pop()
        previous_key = navigation_history[-1]

        # Обновляем состояние
        await state.update_data(
            current_menu=previous_key,
            navigation_history=navigation_history
        )

        logger.debug(f"Back to: {previous_key}, History: {navigation_history}")

        # Определяем тип предыдущей страницы (меню или контент)
        if previous_key.startswith('content:'):
            # Если возвращаемся к контенту
            _, table_id, row_id = previous_key.split(':')
            content, keyboard = await handle_content_button(table_id, row_id)

            if content.get('image_url'):
                await callback_query.message.edit_media(
                    media=types.InputMediaPhoto(
                        media=content['image_url'],
                        caption=content.get('text', ''),
                        parse_mode="HTML"
                    ),
                    reply_markup=keyboard
                )
            else:
                await callback_query.message.edit_text(
                    text=content['text'],
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            # Если возвращаемся к меню
            content, keyboard = await handle_table_menu(previous_key)

            if content.get('image_url'):
                await callback_query.message.edit_media(
                    media=types.InputMediaPhoto(
                        media=content['image_url'],
                        caption=content.get('text', ''),
                        parse_mode="HTML"
                    ),
                    reply_markup=keyboard
                )
            elif content.get('text'):
                await callback_query.message.edit_text(
                    text=content['text'],
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Back navigation error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка возврата", show_alert=True)



@router.callback_query(lambda c: c.data.startswith('submenu:'))
async def process_submenu_callback(callback_query: types.CallbackQuery):
    """Обработчик нажатия на кнопки подменю"""
    table_id = callback_query.data.split(':')[1]
    logger.info(f"Обработка callback подменю для table_id={table_id}")

    content, keyboard = await handle_table_menu(table_id)

    if not keyboard:
        logger.error(f"Не удалось получить клавиатуру для table_id={table_id}")
        await callback_query.answer("Ошибка загрузки меню", show_alert=True)
        return

    try:
        if content.get('image_url'):
            media = types.InputMediaPhoto(
                media=content['image_url'],
                caption=content.get('text', ''),
                parse_mode="HTML"
            )
            await callback_query.message.edit_media(media=media, reply_markup=keyboard)
        elif content.get('text'):
            await callback_query.message.edit_text(
                text=content['text'],
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)

        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при обработке callback подменю: {str(e)}")
        await callback_query.answer("Произошла ошибка", show_alert=True)