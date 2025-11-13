import logging
from typing import List, Dict

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from app.services.fsm import state_manager
from app.services.broadcast import is_user_admin, get_broadcast_notifications, get_active_users, prepare_notification_content
from telegram.handlers.handler_base import start_navigation

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Команда запускает выбор уведомления из тех, что есть в таблице Уведомления"""
    try:
        await state_manager.clear(message.from_user.id)

        # Проверяем права администратора
        if not await is_user_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для этой команды")
            return

        # Получаем список уведомлений из Seatable
        notifications = await get_broadcast_notifications()
        if not notifications:
            await message.answer("Нет уведомлений для рассылки")
            return

        # Создаем клавиатуру с названиями уведомлений
        keyboard = await create_broadcast_keyboard(notifications)

        await message.answer(
            "Выберите уведомление для рассылки. ❗️ ВНИМАНИЕ: После нажатия на кнопку сообщение отправится пользователям.",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Broadcast command error: {str(e)}")
        await message.answer("Ошибка при загрузке уведомлений")


async def create_broadcast_keyboard(notifications: List[Dict]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с названиями уведомлений"""
    inline_keyboard = []

    for notification in notifications:
        name = notification.get('Name', 'Без названия')
        row_id = notification.get('_id')

        if name and row_id:
            inline_keyboard.append([
                InlineKeyboardButton(
                    text=name,
                    callback_data=f"broadcast:{row_id}"
                )
            ])

    # Добавляем кнопку отмены
    inline_keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.callback_query(F.data.startswith("broadcast:"))
async def handle_broadcast_selection(callback_query: CallbackQuery, bot: Bot):
    """Обрабатывает выбор уведомления для рассылки и делает рассылку"""
    try:
        # Извлекаем ID выбранного уведомления
        notification_id = callback_query.data.replace("broadcast:", "")

        # Получаем данные уведомления
        notifications = await get_broadcast_notifications()
        selected_notification = next(
            (n for n in notifications if n.get('_id') == notification_id),
            None
        )

        if not selected_notification:
            await callback_query.answer("Уведомление не найдено", show_alert=True)
            return

        # Убираем клавиатуру
        await callback_query.message.edit_reply_markup(reply_markup=None)

        # Запускаем рассылку
        await callback_query.message.answer(
            f"Запускаю рассылку: {selected_notification.get('Name', 'Без названия')}"
        )

        success = await send_broadcast_to_all_users(selected_notification, bot)

        if success:
            await callback_query.message.answer("✅ Рассылка завершена!")
        else:
            await callback_query.message.answer("❌ Ошибка при рассылке")

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Broadcast selection error: {str(e)}")
        await callback_query.answer("Ошибка при запуске рассылки", show_alert=True)


@router.callback_query(F.data == "broadcast_cancel")
async def handle_broadcast_cancel(callback_query: CallbackQuery):
    """Обрабатывает отмену рассылки"""
    await callback_query.message.edit_reply_markup(reply_markup=None)

    # Создаем клавиатуру с кнопкой возврата в меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⬅️ В главное меню",
            callback_data="broadcast_back_to_menu"
        )
    ]])

    await callback_query.message.answer(
        "Рассылка отменена",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def send_broadcast_to_all_users(notification: Dict, bot: Bot) -> bool:
    """Отправляет уведомление всем активным пользователям"""
    try:
        # Получаем активных пользователей
        active_users = await get_active_users()
        logger.info(f"Начинаю рассылку '{notification.get('Name')}' для {len(active_users)} пользователей")

        # Подготавливаем контент один раз для всех пользователей
        content, file_data, filename = await prepare_notification_content(notification)

        # Создаем клавиатуру с кнопкой (один раз для всех пользователей)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="Ок 👍 Вернуться в меню",
                callback_data="broadcast_back_to_menu"
            )
        ]])

        # Отправляем каждому пользователю
        success_count = 0
        for user in active_users:
            try:
                user_id = int(user['ID_messenger'])

                # Отправляем файл (если есть)
                if file_data:
                    await send_telegram_file(user_id, file_data, filename, bot)

                # Отправляем контент
                await send_telegram_content(user_id, content, bot, keyboard)

                logger.info(f"Отправлено пользователю {user_id}")
                success_count += 1

            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user['ID_messenger']}: {str(e)}")

        logger.info(f"Рассылка завершена. Успешно: {success_count}/{len(active_users)}")
        return True

    except Exception as e:
        logger.error(f"Broadcast error: {str(e)}")
        return False


async def send_telegram_content(user_id: int, content: Dict, bot: Bot, keyboard: InlineKeyboardMarkup = None):
    """Отправляет контент пользователю в Telegram"""
    if content.get('image_url'):
        await bot.send_photo(
            chat_id=user_id,
            photo=content['image_url'],
            caption=content.get('text', ''),
            parse_mode="HTML",
            reply_markup=keyboard
        )
    elif content.get('text'):
        await bot.send_message(
            chat_id=user_id,
            text=content.get('text', ''),
            parse_mode="HTML",
            reply_markup=keyboard
        )


async def send_telegram_file(user_id: int, file_data: bytes, filename: str, bot: Bot):
    """Отправляет файл пользователю в Telegram"""
    file_to_send = BufferedInputFile(file_data, filename=filename)
    await bot.send_document(chat_id=user_id, document=file_to_send)


@router.callback_query(F.data == "broadcast_back_to_menu")
async def handle_broadcast_back_to_menu(callback_query: CallbackQuery):
    """Обрабатывает кнопку возврата в меню из рассылки"""
    try:
        # Запускаем навигацию (аналогично команде /start)
        await start_navigation(message=callback_query.message)

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Ошибка обработки кнопки возврата в меню: {str(e)}")
        await callback_query.answer("Ошибка возврата в меню", show_alert=True)