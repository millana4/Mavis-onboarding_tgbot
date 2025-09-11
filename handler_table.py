import re
import logging
from typing import List, Dict, Optional, Tuple
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext

from config import Config
from handler_form import _process_form, _is_form
from seatable_api_base import fetch_table
from utils import prepare_telegram_message, download_and_send_file

router = Router()
logger = logging.getLogger(__name__)


async def handle_table_menu(table_id: str = Config.SEATABLE_MAIN_MENU_ID,
                          message: Message = None,
                          state: FSMContext = None) -> Tuple[Dict, InlineKeyboardMarkup]:
    """
    Обрабатывает данные таблицы и создает Telegram-сообщение с меню или формой
    """
    logger.info(f"Начало обработки меню для table_id={table_id}")

    table_data = await fetch_table(table_id)
    if not table_data:
        logger.warning(f"Не удалось загрузить данные для table_id={table_id}")
        return {"text": "Не удалось загрузить данные"}, None

    # Ветвление — обрабатывается форма или обычное меню
    if _is_form(table_data):
        logger.info(f"Таблица {table_id} идентифицирована как форма")
        if message and state:  # Проверяем наличие необходимых аргументов
            return await _process_form(table_data, message, state)
        else:
            logger.error("Для работы формы требуется message и state")
            return {"text": "Ошибка инициализации формы"}, None
    else:
        logger.info(f"Таблица {table_id} - обычное меню")
        # Логика обработки меню
        content_part = await _process_content_part(table_data)
        keyboard = await _create_menu_keyboard(table_data, table_id)

        if 'parse_mode' not in content_part:
            content_part['parse_mode'] = 'HTML'

        # Если контента нет - возвращаем пустой текст
        if not content_part.get('text') and not content_part.get('image_url'):
            content_part['text'] = ''

        return content_part, keyboard


async def _process_content_part(table_data: List[Dict]) -> Dict:
    """Обрабатывает контентную часть (Info)"""
    logger.info("Поиск контентной части (Info) в данных таблицы")

    for row in table_data:
        if row.get('Name') == 'Info' and row.get('Content'):
            logger.info("Найдена строка с контентом (Info)")
            return prepare_telegram_message(row['Content'])

    logger.info("Строка с контентом (Info) не найдена")
    return {"text": ""}


async def _create_menu_keyboard(table_data: List[Dict], current_table_id: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопками"""
    inline_keyboard = []

    for row in table_data:
        name = row.get('Name')
        if not name or name == 'Info':
            continue

        if row.get('Submenu_link') and Config.SEATABLE_ATS_APP in row.get('Submenu_link'):
            # В Submenu_link может быть ссылка на справочник сотрудников
            submenu_id = re.search(r'tid=([^&]+)', row['Submenu_link']).group(1)
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                callback_data=f"ats:{submenu_id}"
            )])
        elif row.get('Submenu_link'):
            # Или в Submenu_link может быть ссылка на другое меню
            submenu_id = re.search(r'tid=([^&]+)', row['Submenu_link']).group(1)
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                callback_data=f"menu:{submenu_id}"
            )])
        elif row.get('External_link'):
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                url=row['External_link']
            )])
        elif row.get('Button_content'):
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                callback_data=f"content:{current_table_id}:{row['_id']}"
            )])

    # Добавляем кнопку "Назад" только если это не главное меню
    if current_table_id != Config.SEATABLE_MAIN_MENU_ID:
        inline_keyboard.append([InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"
        )])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# Хендлер для кнопок меню
@router.callback_query(lambda c: c.data.startswith('menu:'))
async def process_menu_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик перехода между меню"""
    try:
        # Получаем и обновляем состояние
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [Config.SEATABLE_MAIN_MENU_ID])
        new_table_id = callback_query.data.split(':')[1]

        navigation_history.append(new_table_id, )
        await state.update_data(
            current_menu=new_table_id,
            navigation_history=navigation_history
        )

        # Получаем данные меню
        content, keyboard = await handle_table_menu(
            new_table_id,
            message=callback_query.message,
            state=state
        )

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


async def handle_content_button(table_id: str, row_id: str) -> Tuple[Dict, Optional[InlineKeyboardMarkup]]:
    """
    Обрабатывает нажатие на кнопку контента
    :return: Кортеж (контент, клавиатура "Назад")
    """
    logger.info(f"Обработка контента для table_id={table_id}, row_id={row_id}")

    table_data = await fetch_table(table_id)
    if not table_data:
        logger.error(f"Ошибка загрузки данных таблицы {table_id}")
        return {"text": "Ошибка загрузки контента"}, None

    row = next((r for r in table_data if r['_id'] == row_id), None)
    if not row:
        logger.error(f"Строка с row_id={row_id} не найдена в таблице {table_id}")
        return {"text": "Контент не найден"}, None

    logger.info(f"Найдена строка контента: {row.get('Name', 'Без названия')}")

    # Подготавливаем контент
    content = {}
    if row.get('Button_content'):
        content.update(prepare_telegram_message(row['Button_content']))
        logger.info("Контент подготовлен")

    # Создаем клавиатуру "Назад" (теперь без параметров)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"  # Убрали параметры
        )
    ]])
    logger.info("Создана клавиатура 'Назад'")

    return content, keyboard