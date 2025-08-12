from aiogram import Router, types
from aiogram.filters import Command
from table_handlers import handle_table_menu, handle_content_button
from seatable_api import fetch_table
from utils import download_and_send_file
import logging

# Создаем роутер
router = Router()
logger = logging.getLogger(__name__)


# Хендлер команды /start
@router.message(Command("start"))
async def send_welcome(message: types.Message):
    try:
        content, keyboard = await handle_table_menu()

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
async def process_menu_callback(callback_query: types.CallbackQuery):
    """Обработчик нажатия на кнопки меню"""
    table_id = callback_query.data.split(':')[1]
    logger.info(f"Обработка callback меню для table_id={table_id} от пользователя {callback_query.from_user.id}")

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
        logger.error(f"Ошибка при обработке callback меню: {str(e)}")
        await callback_query.answer("Произошла ошибка", show_alert=True)
        raise


@router.callback_query(lambda c: c.data.startswith('content:'))
async def process_content_callback(callback_query: types.CallbackQuery):
    """Обработчик нажатия на кнопки контента"""
    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {str(e)}")

    _, table_id, row_id = callback_query.data.split(':')
    user_id = callback_query.from_user.id
    logger.info(f"Обработка контента table_id={table_id}, row_id={row_id} для пользователя {user_id}")

    try:
        # Получаем данные строки
        table_data = await fetch_table(table_id)
        row = next((r for r in table_data if r['_id'] == row_id), None)

        # Обработка вложения, если оно есть
        if row and row.get('Attachment'):
            file_url = row['Attachment']  # теперь берём всю строку
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
@router.callback_query(lambda c: c.data.startswith('back:'))
async def process_back_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки 'Назад'"""
    try:
        _, table_id, row_id = callback_query.data.split(':')
        logger.info(f"Обработка кнопки Назад для table_id={table_id}, row_id={row_id}")

        # Получаем контент кнопки
        content, _ = await handle_content_button(table_id, row_id)

        # Отправляем контент в чат
        if content.get('image_url'):
            await callback_query.message.answer_photo(
                photo=content['image_url'],
                caption=content.get('text', ''),
                parse_mode="HTML"
            )
        elif content.get('text'):
            await callback_query.message.answer(
                text=content['text'],
                parse_mode="HTML"
            )

        # Удаляем сообщение с кнопкой "Назад"
        await callback_query.message.delete()

        # Загружаем родительское меню
        parent_table_id = table_id.split(':')[0] if ':' in table_id else '0000'
        menu_content, menu_keyboard = await handle_table_menu(parent_table_id)

        # Отправляем родительское меню
        if menu_content.get('image_url'):
            await callback_query.message.answer_photo(
                photo=menu_content['image_url'],
                caption=menu_content.get('text', ''),
                reply_markup=menu_keyboard,
                parse_mode="HTML"
            )
        elif menu_content.get('text'):
            await callback_query.message.answer(
                text=menu_content['text'],
                reply_markup=menu_keyboard,
                parse_mode="HTML"
            )
        else:
            await callback_query.message.answer(
                text="Меню",
                reply_markup=menu_keyboard
            )

        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Назад': {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка", show_alert=True)


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