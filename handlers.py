from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from form_handler import finish_form, ask_next_question
from table_handlers import handle_table_menu, handle_content_button
from seatable_api import fetch_table
from utils import download_and_send_file, prepare_telegram_message
import logging

# Создаем роутер
router = Router()
logger = logging.getLogger(__name__)


class Navigation(StatesGroup):
    current_menu = State()  # Хранит текущее меню и историю для каждого пользователя
    form_data = State()  # Состояние для формы

# Хендлер команды /start
@router.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    """Обработчик команды /start с инициализацией FSM"""
    try:
        # Инициализируем состояние навигации
        await state.update_data(
            current_menu=Config.SEATABLE_MAIN_MENU_ID,
            navigation_history=[Config.SEATABLE_MAIN_MENU_ID]
        )

        content, keyboard = await handle_table_menu(Config.SEATABLE_MAIN_MENU_ID, message=message, state=state)

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
            else:
                await callback_query.message.answer(
                    text="Меню",
                    **kwargs
                )
        elif keyboard:
            await callback_query.message.answer(
                text="Меню",
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


# Хендлер кнопки "Назад"
@router.callback_query(lambda c: c.data == 'back')
async def process_back_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад'"""
    try:
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [])

        if len(navigation_history) <= 1:
            await callback_query.answer("Вы в главном меню")
            return

        # Получаем текущий контент (если мы на content)
        current_key = navigation_history[-1]
        button_content = None
        if current_key.startswith('content:'):
            _, current_table_id, current_row_id = current_key.split(':')

            # Получаем конкретный Button_content текущей строки
            current_table_data = await fetch_table(current_table_id)
            current_row = next((r for r in current_table_data if r['_id'] == current_row_id), None)
            if current_row and current_row.get('Button_content'):
                button_content = prepare_telegram_message(current_row['Button_content'])

        # Получаем предыдущий экран
        previous_key = navigation_history[-2]
        await state.update_data(
            current_menu=previous_key,
            navigation_history=navigation_history[:-1]
        )

        # Удаляем текущее сообщение
        try:
            await callback_query.message.delete()
        except:
            pass

        # Если был контент - постим его Button_content перед возвратом
        if button_content:
            if button_content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=button_content['image_url'],
                    caption=button_content.get('text', ' '),
                    parse_mode="HTML"
                )
            elif button_content.get('text'):
                await callback_query.message.answer(
                    text=button_content['text'],
                    parse_mode="HTML"
                )

        # Возвращаемся к предыдущему экрану
        if previous_key.startswith('content:'):
            # Возврат к контенту
            _, table_id, row_id = previous_key.split(':')
            content, keyboard = await handle_content_button(table_id, row_id)

            if content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=content.get('text', "Информация"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback_query.message.answer(
                    text=content.get('text', "Информация"),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            # Возврат к меню
            content, keyboard = await handle_table_menu(previous_key)

            menu_text = content.get('text', "Меню") if content else "Меню"

            if content and content.get('image_url'):
                await callback_query.message.answer_photo(
                    photo=content['image_url'],
                    caption=menu_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback_query.message.answer(
                    text=menu_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Back error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка возврата", show_alert=True)


@router.callback_query(lambda c: c.data.startswith('form_opt:'))
async def handle_form_option(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор варианта в форме"""
    data = await state.get_data()
    if 'form_data' not in data:
        await callback.answer()
        return

    # Получаем выбранный вариант
    answer = callback.data.split(':', 1)[1]

    # Обновляем состояние формы
    form_data = data['form_data']
    form_data['answers'].append(answer)
    form_data['current_question'] += 1

    await state.update_data(form_data=form_data)
    await callback.message.delete()

    # Переходим к следующему вопросу или завершаем
    if form_data['current_question'] >= len(form_data['questions']):
        await finish_form(callback.message, form_data)
    else:
        await ask_next_question(callback.message, form_data)


@router.message()
async def handle_text_answer(message: types.Message, state: FSMContext):
    """Обрабатывает текстовые ответы в форме"""
    data = await state.get_data()
    if 'form_data' not in data:
        return

    form_data = data['form_data']
    current_question = form_data['current_question']

    # Проверяем, ожидаем ли мы текстовый ответ
    if current_question >= len(form_data['questions']):
        return

    if not form_data['questions'][current_question].get('Free_input', True):
        return

    # Обновляем и сохраняем состояние формы
    form_data['answers'].append(message.text)
    form_data['current_question'] += 1
    await state.update_data({'form_data': form_data})

    # Переходим к следующему вопросу или завершаем
    if form_data['current_question'] >= len(form_data['questions']):
        await finish_form(message, form_data)
        await state.update_data({'form_data': None})  # Очищаем состояние формы
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

    # Обновляем состояние формы
    form_data['answers'].append(answer)
    form_data['current_question'] += 1
    await state.update_data({'form_data': form_data})

    await callback.message.delete()

    # Переходим к следующему вопросу или завершаем
    if form_data['current_question'] >= len(form_data['questions']):
        await finish_form(callback.message, form_data)
        await state.update_data({'form_data': None})  # Очищаем состояние формы
    else:
        await ask_next_question(callback.message, form_data)