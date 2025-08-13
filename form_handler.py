import logging

from aiogram.types import Message
from typing import List, Dict, Optional, Tuple

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from utils import prepare_telegram_message

logger = logging.getLogger(__name__)


async def _process_form(table_data: List[Dict], message: Message, state: FSMContext) -> Tuple[Dict, None]:
    """Обрабатывает данные формы"""
    logger.info("Начало обработки формы обратной связи")
    info_row = next((row for row in table_data if row.get('Name') == 'Info'), None)

    if not info_row:
        logger.error("Форма не содержит строки с Name='Info'")
        return {"text": "Ошибка: форма не настроена правильно"}, None

    # Инициализируем состояние формы
    form_data = await start_form_questions(message.from_user.id, table_data)
    await state.set_data({
        **await state.get_data(),  # Сохраняем существующие данные
        'form_data': form_data     # Добавляем данные формы
    })

    # Подготавливаем контент как в обычном меню
    form_content = prepare_telegram_message(info_row.get('Content', ''))

    # Запускаем первый вопрос
    await ask_next_question(message, form_data)

    return form_content, None


async def start_form_questions(user_id: int, table_data: List[Dict]) -> Dict:
    """Инициализирует процесс опроса формы"""
    questions = [row for row in table_data
                 if row.get('Name') not in ['Info', 'Final_message']]

    return {
        "user_id": user_id,
        "questions": questions,
        "current_question": 0,
        "answers": [],
        "answers_table": next(
            (row['Answers_table'] for row in table_data
             if row.get('Name') == 'Info'), None),
        "final_message": next(
            (row['Content'] for row in table_data
             if row.get('Name') == 'Final_message'), None)
    }


async def get_form_question(form_state: Dict) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает текущий вопрос формы и клавиатуру (если нужно)"""
    question_data = form_state['questions'][form_state['current_question']]
    question_text = question_data['Name']

    if question_data.get('Free_input', True):
        return question_text, None  # Текстовый ответ

    # Создаем кнопки для вариантов ответа
    options = [
        question_data[f'Answer_option_{i}']
        for i in range(1, 6)
        if question_data.get(f'Answer_option_{i}')
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"form_opt:{opt}")]
        for opt in options
    ])

    return question_text, keyboard


async def complete_form(form_state: Dict) -> Dict:
    """Формирует финальные данные формы"""
    return {
        "user_id": form_state["user_id"],
        "answers": [
            {"question": q["Name"], "answer": a}
            for q, a in zip(form_state["questions"], form_state["answers"])
        ],
        "answers_table": form_state["answers_table"],
        "final_message": form_state["final_message"]
    }


async def ask_next_question(message: Message, form_data: Dict):
    """Задает следующий вопрос формы"""
    question_text, keyboard = await get_form_question(form_data)

    if keyboard:
        await message.answer(question_text, reply_markup=keyboard)
    else:
        await message.answer(question_text)


async def finish_form(message: Message, form_data: Dict):
    """Завершает форму и показывает финальное сообщение"""
    result = await complete_form(form_data)

    # Отправляем финальное сообщение
    if form_data.get('final_message'):
        content = prepare_telegram_message(form_data['final_message'])
        await message.answer(**content)

    # Здесь потом добавим сохранение результата (result)
    logger.info(f"Форма завершена: {result}")