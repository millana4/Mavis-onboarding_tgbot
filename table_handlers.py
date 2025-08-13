from typing import List, Dict, Optional, Tuple
import re
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext

from config import Config
from form_handler import _process_form
from seatable_api import fetch_table
from utils import prepare_telegram_message

logger = logging.getLogger(__name__)


def _is_form(table_data: List[Dict]) -> bool:
    """Проверяет, является ли таблица формой"""
    return any('Answers_table' in row and row['Answers_table'] for row in table_data)


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

    # Ветвление: форма или обычное меню
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

        if row.get('Submenu_link'):
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