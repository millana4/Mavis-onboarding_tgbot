from aiogram import Router, types
from aiogram.filters import Command
from table_handlers import handle_table_menu, handle_content_button
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

    if not content or not keyboard:
        logger.error(f"Не удалось получить контент или клавиатуру для table_id={table_id}")
        await callback_query.answer("Ошибка загрузки меню", show_alert=True)
        return

    try:
        if content.get('image_url'):
            await callback_query.message.edit_media(
                media=types.InputMediaPhoto(
                    media=content['image_url'],
                    caption=content['text'],
                    parse_mode="Markdown"
                ),
                reply_markup=keyboard
            )
            logger.debug(f"Обновлено медиа с изображением: {content['image_url']}")
        else:
            await callback_query.message.edit_text(
                text=content['text'],
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            logger.debug("Обновлен текстовый контент")

        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при обработке callback меню: {str(e)}")
        await callback_query.answer("Произошла ошибка", show_alert=True)
        raise


# Хендлер для кнопок контента (показ контента)
@router.callback_query(lambda c: c.data.startswith('content:'))
async def process_content_callback(callback_query: types.CallbackQuery):
    """Обработчик нажатия на кнопки контента"""
    _, table_id, row_id = callback_query.data.split(':')
    logger.info(
        f"Обработка callback контента table_id={table_id}, row_id={row_id} от пользователя {callback_query.from_user.id}")

    content, keyboard = await handle_content_button(table_id, row_id)

    if not content:
        logger.error(f"Не удалось получить контент для row_id={row_id}")
        await callback_query.answer("Ошибка загрузки контента", show_alert=True)
        return

    try:
        # Определяем тип контента и отправляем соответствующее сообщение
        if content.get('document'):
            # Отправка документа с проверкой caption
            caption = content.get('text', '')
            await callback_query.message.answer_document(
                document=content['document'],
                caption=caption[:1024] if caption else None,  # Ограничение длины caption в Telegram
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.debug(f"Отправлен документ: {content['document']}, caption length: {len(caption)}")

        elif content.get('image_url'):
            # Проверяем наличие текста для caption
            if not content.get('text'):
                logger.warning("Отправка фото без текста caption")

            await callback_query.message.answer_photo(
                photo=content['image_url'],
                caption=content.get('text', '')[:1024],  # Ограничение длины
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.debug(f"Отправлено фото: {content['image_url']}")

        else:
            # Проверяем наличие текста
            if not content.get('text'):
                logger.error("Попытка отправить пустое текстовое сообщение")
                await callback_query.answer("Ошибка: пустой текст", show_alert=True)
                return

            await callback_query.message.answer(
                text=content['text'],
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.debug(f"Отправлен текст, длина: {len(content['text'])}")

        # Подтверждаем обработку callback
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Ошибка при отправке контента: {str(e)}", exc_info=True)
        await callback_query.answer("Произошла ошибка при отправке", show_alert=True)


# Хендлер кнопки "Назад"
@router.callback_query(lambda c: c.data == 'back')
async def process_back_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки 'Назад'"""
    logger.info(f"Обработка кнопки 'Назад' от пользователя {callback_query.from_user.id}")
    try:
        await process_menu_callback(callback_query)
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Назад': {str(e)}")
        await callback_query.answer("Произошла ошибка", show_alert=True)
        raise
