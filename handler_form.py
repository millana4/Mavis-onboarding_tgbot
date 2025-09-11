import asyncio
import logging
import pprint

from aiogram import Router, types
from aiogram.types import Message
from typing import List, Dict, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime

from config import Config
from seatable_api_forms import save_form_answers
from utils import prepare_telegram_message


router = Router()
logger = logging.getLogger(__name__)


def _is_form(table_data: List[Dict]) -> bool:
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
        **await state.get_data(),
        'form_data': form_data
    })

    # Подготавливаем контент
    form_content = prepare_telegram_message(info_row.get('Content', ''))

    # Сначала отправляем контент Info и ждём завершения
    if form_content.get('image_url'):
        await message.answer_photo(
            photo=form_content['image_url'],
            caption=form_content.get('text', ''),
            parse_mode=form_content.get('parse_mode', 'HTML')
        )
    elif form_content.get('text'):
        await message.answer(
            text=form_content['text'],
            parse_mode=form_content.get('parse_mode', 'HTML')
        )

    # Задержка перед первым вопросом, чтобы постился после инфо
    await asyncio.sleep(0.5)
    await ask_next_question(message, form_data)

    return {"text": ""}, None  # Возвращаем пустой словарь


async def start_form_questions(user_id: int, table_data: List[Dict]) -> Dict:
    """Инициализирует процесс опроса формы"""
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


async def get_form_question(form_state: Dict) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает текущий вопрос формы и клавиатуру (если нужно)"""
    question_data = form_state['questions'][form_state['current_question']]
    question_text = question_data['Name']

    # Определяем, есть ли варианты ответа (ищем все ключи, начинающиеся на Answer_option_)
    answer_options = {
        k: v for k, v in question_data.items()
        if k.startswith('Answer_option_') and v is not None
    }

    # Если Free_input явно указан как True или есть варианты ответа
    if question_data.get('Free_input', False) is True or not answer_options:
        return question_text, None  # Текстовый ответ

    # Создаем кнопки для вариантов ответа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"form_opt:{opt}")]
        for opt in answer_options.values()
    ])

    return question_text, keyboard


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


async def ask_next_question(message: Message, form_data: Dict):
    """Задает следующий вопрос формы"""
    question_text, keyboard = await get_form_question(form_data)

    # Отправляем вопрос в чат
    if keyboard:
        sent_message = await message.answer(question_text, reply_markup=keyboard)
    else:
        sent_message = await message.answer(question_text)

    # Сохраняем ID отправленного вопроса для последующего редактирования
    form_data['last_question_message_id'] = sent_message.message_id
    return sent_message


@router.message()
async def handle_text_answer(message: types.Message, state: FSMContext):
    """Обрабатывает текстовые ответы в форме обратной связи"""
    data = await state.get_data()
    if 'form_data' not in data:
        return

    form_data = data['form_data']
    current_question = form_data['current_question']

    # Проверяем, ожидаем ли мы текстовый ответ
    if current_question >= len(form_data['questions']):
        return

    question_data = form_data['questions'][current_question]
    answer_options = {
        k: v for k, v in question_data.items()
        if k.startswith('Answer_option_') and v is not None
    }

    if question_data.get('Free_input', False) is False and answer_options:
        return  # Пропускаем, если это вопрос с вариантами


    # Сохраняем ответ
    form_data['answers'].append(message.text)
    form_data['current_question'] += 1
    await state.update_data(form_data=form_data)

    if form_data['current_question'] >= len(form_data['questions']):
        await finish_form(message, form_data, state=state)
        await state.update_data(form_data=None)
    else:
        await ask_next_question(message, form_data)


@router.callback_query(lambda c: c.data.startswith('form_opt:'))
async def handle_form_option(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор варианта в форме"""
    data = await state.get_data()
    if 'form_data' not in data:
        await callback.answer()
        return

    form_data = data['form_data']
    answer = callback.data.split(':', 1)[1]

    # Отправляем выбранный ответ в чат
    question_text = form_data['questions'][form_data['current_question']]['Name']
    await callback.message.answer(f"Ваш ответ: «{answer}»")

    # Сохраняем ответ
    form_data['answers'].append(answer)
    form_data['current_question'] += 1
    await state.update_data(form_data=form_data)

    # Удаляем клавиатуру у вопроса
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    # Переходим к следующему вопросу или завершаем
    if form_data['current_question'] >= len(form_data['questions']):
        await finish_form(callback.message, form_data, state=state)
        await state.update_data(form_data=None)
    else:
        await ask_next_question(callback.message, form_data)
    await callback.answer()


async def finish_form(message: Message, form_data: Dict, state: FSMContext):
    """Завершает форму, сохраняет результат и показывает кнопку меню"""
    # Проверяем наличие обязательных полей
    required_fields = ['answers', 'answers_table']
    if any(field not in form_data for field in required_fields):
        logger.error(
            f"Некорректные данные формы. Отсутствуют поля: {[f for f in required_fields if f not in form_data]}")
        await message.answer("Произошла ошибка при обработке формы")
        return

    # Нормализуем answers если нужно
    if isinstance(form_data['answers'], str):
        try:
            import json
            form_data['answers'] = json.loads(form_data['answers'])
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось преобразовать answers: {e}")
            await message.answer("Ошибка обработки ответов")
            return

    # Добавляем timestamp, если его нет
    if 'timestamp' not in form_data:
        from datetime import datetime
        form_data['timestamp'] = datetime.now().isoformat()

    # Завершаем форму и сохраняем результат
    result = await complete_form(form_data, message.from_user.id)
    logger.info(f"Форма завершена: {result}")

    # Сохраняем ответы в таблицу
    save_success = await save_form_answers({
        **form_data,
        "user_id": message.chat.id  # id пользователя в телеграме, не бота
    })

    # Подготавливаем финальное сообщение
    final_text = "Спасибо за обращение!"
    parse_mode = None

    if form_data.get('final_message'):
        content = prepare_telegram_message(form_data['final_message'])
        final_text = content.get('text', final_text)
        parse_mode = content.get('parse_mode')

    # Создаем клавиатуру для возврата
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ В главное меню",
                callback_data=f"menu:{Config.SEATABLE_MAIN_MENU_ID}"
            )]
        ]
    )

    # Отправляем сообщение с кнопкой
    await message.answer(
        text=final_text,
        reply_markup=keyboard,
        parse_mode=parse_mode
    )

    # Очищаем состояние формы
    await state.update_data(form_data=None)