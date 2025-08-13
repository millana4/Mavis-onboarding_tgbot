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
    """Обработчик перехода между меню"""
    try:
        # Получаем и обновляем состояние
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [Config.SEATABLE_MAIN_MENU_ID])
        new_table_id = callback_query.data.split(':')[1]

        navigation_history.append(new_table_id)
        await state.update_data(
            current_menu=new_table_id,
            navigation_history=navigation_history
        )

        # Получаем данные меню
        content, keyboard = await handle_table_menu(new_table_id)

        # Удаляем предыдущее сообщение и создаем новое
        try:
            await callback_query.message.delete()
        except:
            pass

        # Отправляем новое сообщение с учетом типа контента
        kwargs = {
            'reply_markup': keyboard,
            'parse_mode': 'HTML'
        }

        if content:
            if content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=content.get('text', ' '),
                    **kwargs
                )
            elif content.get('text'):
                await callback_query.message.answer(
                    text=content['text'],
                    **kwargs
                )
            else:
                await callback_query.message.answer(
                    text="Меню",
                    **kwargs
                )
        elif keyboard:
            await callback_query.message.answer(
                text="Меню",
                **kwargs
            )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Menu navigation error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка навигации", show_alert=True)


@router.callback_query(lambda c: c.data.startswith('content:'))
async def process_content_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик контентных кнопок (постит в чат)"""
    try:
        # Получаем параметры контента
        _, table_id, row_id = callback_query.data.split(':')

        # Обновляем историю
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [])
        navigation_history.append(f"content:{table_id}:{row_id}")
        await state.update_data(navigation_history=navigation_history)

        # Получаем данные контента
        table_data = await fetch_table(table_id)
        row = next((r for r in table_data if r['_id'] == row_id), None)

        if not row:
            await callback_query.answer("Контент не найден", show_alert=True)
            return

        # Удаляем предыдущее меню
        try:
            await callback_query.message.delete()
        except:
            pass

        # Отправляем вложение (если есть)
        if row.get('Attachment'):
            await download_and_send_file(
                file_url=row['Attachment'],
                callback_query=callback_query
            )

        # Отправляем основной контент
        content, keyboard = await handle_content_button(table_id, row_id)

        if content.get('image_url'):
            await callback_query.message.answer_photo(
                photo=content['image_url'],
                caption=content.get('text', "Информация"),  # Гарантированный текст
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback_query.message.answer(
                text=content.get('text', "Информация"),
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Content error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка загрузки контента", show_alert=True)


# Хендлер кнопки "Назад"
@router.callback_query(lambda c: c.data == 'back')
async def process_back_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад'"""
    try:
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [])

        if len(navigation_history) <= 1:
            await callback_query.answer("Вы в главном меню")
            return

        # Получаем предыдущий экран
        previous_key = navigation_history[-2]
        await state.update_data(
            current_menu=previous_key,
            navigation_history=navigation_history[:-1]
        )

        # Удаляем текущее сообщение
        try:
            await callback_query.message.delete()
        except:
            pass

        if previous_key.startswith('content:'):
            # Возврат к контенту (постим в чат)
            _, table_id, row_id = previous_key.split(':')
            content, keyboard = await handle_content_button(table_id, row_id)

            if content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=content.get('text', "Информация"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback_query.message.answer(
                    text=content.get('text', "Информация"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            # Возврат к меню
            content, keyboard = await handle_table_menu(previous_key)

            menu_text = content.get('text', "Меню") if content else "Меню"

            if content and content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=menu_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback_query.message.answer(
                    text=menu_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Back error: {str(e)}", exc_info=True)
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