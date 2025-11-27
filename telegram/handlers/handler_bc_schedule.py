import logging
from datetime import datetime
from typing import List, Dict

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.broadcast import is_user_admin
from telegram.handlers.handler_base import start_navigation
from telegram.handlers.handler_broadcast import scheduled_broadcasts

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "/scheduled_broadcasts")
async def handle_scheduled_broadcasts(message: Message):
    """Показывает список отложенных рассылок"""
    try:
        user_id = message.from_user.id

        # Проверяем права администратора
        if not await is_user_admin(user_id):
            await message.answer("❌ У вас нет прав для этой команды")
            return

        # Получаем список запланированных рассылок
        broadcasts_list = await get_scheduled_broadcasts_list()

        if not broadcasts_list:
            # Если нет рассылок, показываем сообщение и кнопку назад
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад", callback_data="bc_schedule_back_to_menu")
            ]])

            await message.answer(
                "Нет запланированных рассылок",
                reply_markup=keyboard
            )
            return

        # Создаем клавиатуру с рассылками
        keyboard = await create_broadcasts_keyboard(broadcasts_list)

        await message.answer(
            "Запланированные рассылки:",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Scheduled broadcasts error: {str(e)}")
        await message.answer("Ошибка при загрузке рассылок")


async def get_scheduled_broadcasts_list() -> List[Dict]:
    """Возвращает список запланированных рассылок в нужном формате"""
    broadcasts_list = []

    for broadcast_id, broadcast_data in scheduled_broadcasts.items():
        broadcasts_list.append({
            'id': broadcast_id,
            'name': broadcast_data['notification_name'],
            'scheduled_time': broadcast_data['scheduled_time'],
            'admin_id': broadcast_data['admin_id']
        })

    # Сортируем по времени отправки
    broadcasts_list.sort(key=lambda x: x['scheduled_time'])

    return broadcasts_list


async def create_broadcasts_keyboard(broadcasts_list: List[Dict]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками рассылок"""
    inline_keyboard = []

    for broadcast in broadcasts_list:
        # Форматируем дату и время
        time_str = broadcast['scheduled_time'].strftime('%d.%m %H:%M')
        button_text = f"{time_str} «{broadcast['name']}»"

        inline_keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"bc_schedule_view:{broadcast['id']}"
            )
        ])

    # Добавляем кнопку назад
    inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="bc_schedule_back_to_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.callback_query(F.data.startswith("bc_schedule_view:"))
async def handle_broadcast_view(callback_query: CallbackQuery):
    """Обрабатывает просмотр конкретной рассылки"""
    try:
        user_id = callback_query.from_user.id
        broadcast_id = callback_query.data.replace("bc_schedule_view:", "")

        # Проверяем права администратора
        if not await is_user_admin(user_id):
            await callback_query.answer("У вас нет прав", show_alert=True)
            return

        # Ищем рассылку
        broadcast_data = scheduled_broadcasts.get(broadcast_id)
        if not broadcast_data:
            await callback_query.answer("Рассылка не найдена", show_alert=True)
            return

        # Форматируем дату и время
        time_str = broadcast_data['scheduled_time'].strftime('%d.%m.%Y в %H:%M')

        # Создаем клавиатуру с действиями
        action_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ ОК", callback_data=f"bc_schedule_ok:{broadcast_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"bc_schedule_cancel:{broadcast_id}")
            ]
        ])

        await callback_query.message.edit_text(
            f"Уведомление: «{broadcast_data['notification_name']}»\n"
            f"Запланировано на: {time_str}",
            reply_markup=action_keyboard
        )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Broadcast view error: {str(e)}")
        await callback_query.answer("Ошибка при загрузке рассылки", show_alert=True)


@router.callback_query(F.data.startswith("bc_schedule_ok:"))
async def handle_broadcast_ok(callback_query: CallbackQuery):
    """Обрабатывает подтверждение просмотра рассылки"""
    try:
        user_id = callback_query.from_user.id
        broadcast_id = callback_query.data.replace("bc_schedule_ok:", "")

        # Проверяем права администратора
        if not await is_user_admin(user_id):
            await callback_query.answer("❌ У вас нет прав", show_alert=True)
            return

        # Ищем рассылку
        broadcast_data = scheduled_broadcasts.get(broadcast_id)
        if not broadcast_data:
            await callback_query.answer("Рассылка не найдена", show_alert=True)
            return

        # Форматируем дату и время
        time_str = broadcast_data['scheduled_time'].strftime('%d.%m.%Y в %H:%M')

        # Создаем клавиатуру для возврата в меню
        menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ В главное меню", callback_data="bc_schedule_back_to_menu")
        ]])

        await callback_query.message.edit_text(
            f"Уведомление «{broadcast_data['notification_name']}» будет отправлено {time_str}.",
            reply_markup=menu_keyboard
        )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Broadcast OK error: {str(e)}")
        await callback_query.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("bc_schedule_cancel:"))
async def handle_broadcast_cancel(callback_query: CallbackQuery, bot: Bot):
    """Обрабатывает отмену просмотра рассылки"""
    try:
        user_id = callback_query.from_user.id
        broadcast_id = callback_query.data.replace("bc_schedule_cancel:", "")

        # Проверяем права администратора
        if not await is_user_admin(user_id):
            await callback_query.answer("❌ У вас нет прав", show_alert=True)
            return

        # Ищем рассылку
        broadcast_data = scheduled_broadcasts.get(broadcast_id)
        if not broadcast_data:
            await callback_query.answer("Рассылка не найдена", show_alert=True)
            return

        # Отменяем рассылку
        from telegram.handlers.handler_broadcast import cancel_scheduled_broadcast
        success = await cancel_scheduled_broadcast(broadcast_id)

        # Создаем клавиатуру для возврата в меню
        menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ В главное меню", callback_data="bc_schedule_back_to_menu")
        ]])

        if success:
            await callback_query.message.edit_text(
                f"Отправка уведомления «{broadcast_data['notification_name']}» отменена.",
                reply_markup=menu_keyboard
            )
        else:
            await callback_query.message.edit_text(
                f"⚠️ Не удалось отменить рассылку «{broadcast_data['notification_name']}».",
                reply_markup=menu_keyboard
            )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Broadcast cancel error: {str(e)}")
        await callback_query.answer("Ошибка при отмене рассылки", show_alert=True)


@router.callback_query(F.data == "bc_schedule_back_to_menu")
async def handle_back_to_menu(callback_query: CallbackQuery):
    """Обрабатывает возврат в главное меню"""
    try:
        await start_navigation(message=callback_query.message)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Back to menu error: {str(e)}")
        await callback_query.answer("Ошибка возврата в меню", show_alert=True)