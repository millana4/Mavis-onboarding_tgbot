import re
import logging
from typing import List, Dict, Optional, Tuple
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from config import Config
from app.services.fsm import state_manager
from app.services.cache_access import check_user_access, RESTRICTING_MESSAGE
from app.seatable_api.api_base import fetch_table
from telegram.handlers.handler_form import _process_form, _is_form
from telegram.utils import prepare_telegram_message
from telegram.handlers.handler_table import _create_menu_keyboard
from utils import download_and_send_file

logger = logging.getLogger(__name__)


async def process_content_part(table_data: List[Dict]) -> Dict:
    """Обрабатывает контентную часть (Info)"""
    logger.info("Поиск контентной части (Info) в данных таблицы")

    for row in table_data:
        if row.get('Name') == 'Info' and row.get('Content'):
            logger.info("Найдена строка с контентом (Info)")
            return prepare_telegram_message(row['Content'])

    logger.info("Строка с контентом (Info) не найдена")
    return {"text": ""}