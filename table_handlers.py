from typing import List, Dict, Optional, Tuple
import re
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from seatable_api import fetch_table
from utils import prepare_telegram_message

logger = logging.getLogger(__name__)


async def handle_table_menu(table_id: str = '0000', is_back: bool = False) -> Tuple[Dict, InlineKeyboardMarkup]:
    """
    Обрабатывает данные таблицы и создает Telegram-сообщение с меню
    :param table_id: ID таблицы (по умолчанию '0000' - главное меню)
    :param is_back: Флаг возврата из подменю (для кнопки "Назад")
    :return: Кортеж (контент, клавиатура)
    """
    logger.info(f"Начало обработки меню для table_id={table_id}, is_back={is_back}")

    # Получаем данные таблицы
    table_data = await fetch_table(table_id)
    if not table_data:
        logger.warning(f"Не удалось загрузить данные для table_id={table_id}")
        return {"text": "Не удалось загрузить данные"}, None

    logger.info(f"Успешно загружено {len(table_data)} строк из таблицы {table_id}")

    # 1. Обрабатываем контентную часть (Info)
    content_part = await _process_content_part(table_data)
    logger.info(f"Контентная часть подготовлена: {bool(content_part.get('text'))}")

    # 2. Создаем инлайн-кнопки
    keyboard = await _create_menu_keyboard(table_data, table_id, is_back)
    logger.info(f"Клавиатура создана, кнопок: {len(keyboard.inline_keyboard)} строк")

    content_part = await _process_content_part(table_data)
    if 'parse_mode' not in content_part:
        content_part['parse_mode'] = 'HTML'  # Добавляем parse_mode если его нет
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


async def _create_menu_keyboard(table_data: List[Dict], current_table_id: str, is_back: bool) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопками"""
    logger.info(f"Создание клавиатуры для table_id={current_table_id}")

    inline_keyboard = []
    button_types = {'submenu': 0, 'external': 0, 'content': 0}

    for row in table_data:
        name = row.get('Name')
        if not name or name == 'Info':
            continue

        # Создаем кнопку и добавляем в отдельный ряд
        if row.get('Submenu_link'):
            submenu_id = re.search(r'tid=([^&]+)', row['Submenu_link']).group(1)
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                callback_data=f"submenu:{submenu_id}"
            )])
            button_types['submenu'] += 1
        elif row.get('External_link'):
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                url=row['External_link']
            )])
            button_types['external'] += 1
        else:
            inline_keyboard.append([InlineKeyboardButton(
                text=name,
                callback_data=f"content:{current_table_id}:{row['_id']}"
            )])
            button_types['content'] += 1

    # Добавляем кнопку "Назад" в отдельный ряд
    if current_table_id != '0000' or is_back:
        inline_keyboard.append([InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    logger.info(f"Создана клавиатура: {button_types['submenu']} подменю, "
                f"{button_types['external']} внешних, {button_types['content']} контентных кнопок")

    return keyboard


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

    # Добавляем файл если есть
    if row.get('Attachment'):
        content['document'] = row['Attachment']
        logger.info(f"Добавлен файл: {content['document']}")

    # Создаем клавиатуру "Назад"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"back:{table_id}:{row_id}"
        )
    ]])
    logger.info("Создана клавиатура 'Назад'")

    return content, keyboard