import asyncio
import logging

from aiogram import Router, types
from aiogram.types import Message
from aiogram.filters import StateFilter
from typing import List, Dict, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime

from app.services.cache_access import check_user_access, RESTRICTING_MESSAGE
from config import Config
from app.seatable_api.api_forms import save_form_answers
from telegram.utils import prepare_telegram_message


logger = logging.getLogger(__name__)


def is_form(table_data: List[Dict]) -> bool:
    """Проверяет, является ли таблица формой"""
    has_form_fields = False
    for row in table_data:
        # Если есть признаки меню - точно не форма
        if any(field in row for field in ['Submenu_link', 'Button_content', 'External_link']):
            return has_form_fields

        # Проверяем признаки формы
        if ('Free_input' in row) or any(key.startswith('Answer_option_') for key in row.keys()):
            has_form_fields = True

    # Answers_table проверяем только в строке Info
    info_row = next((row for row in table_data if row.get('Name') == 'Info'), {})
    if info_row.get('Answers_table'):
        has_form_fields = True

    return has_form_fields


async def start_form_questions(table_data: List[Dict]) -> Dict:
    """Получает вопросы из формы"""
    questions = [row for row in table_data
                if row.get('Name') not in ['Info', 'Final_message']]

    # Безопасное получение answers_table (может быть None)
    info_row = next((row for row in table_data if row.get('Name') == 'Info'), {})
    answers_table = info_row.get('Answers_table')

    # Безопасное получение final_message (может быть None)
    final_row = next((row for row in table_data if row.get('Name') == 'Final_message'), {})
    final_message = final_row.get('Content')

    return {
        "questions": questions,
        "current_question": 0,
        "answers": [],
        "answers_table": answers_table,  # Может быть None
        "final_message": final_message  # Может быть None
    }


async def complete_form(form_state: Dict, user_id: int) -> Dict:
    """Формирует финальные данные формы с корректным user_id"""
    return {
        "user_id": user_id,  # Используем переданный user_id (из message.chat.id)
        "questions": form_state["questions"],  # Добавляем вопросы в результат
        "answers": form_state["answers"],
        "answers_table": form_state["answers_table"],
        "final_message": form_state.get("final_message"),
        "timestamp": datetime.now().isoformat()
    }