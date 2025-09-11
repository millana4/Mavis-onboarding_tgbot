import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import StateFilter

from config import Config
from handlers import start_navigation
from keyboards import search_kb, BTN_DEPARTMENT_SEARCH, BTN_EMPLOYEE_SEARCH, BTN_BACK

router = Router()
logger = logging.getLogger(__name__)


# Добавляем состояние для поиска
class SearchState(StatesGroup):
    waiting_for_search_type = State()
    waiting_for_name_search = State()
    waiting_for_department_search = State()


# Хендлер для кнопки со справочником сотрудников
@router.callback_query(lambda c: c.data.startswith('ats:'))
async def process_ats_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие на кнопку со справочником"""
    try:
        # Получаем и обновляем состояние
        data = await state.get_data()
        navigation_history = data.get('navigation_history', [Config.SEATABLE_MAIN_MENU_ID])
        ats_tag = callback_query.data.split(':')[1]

        navigation_history.append(ats_tag)
        await state.update_data(
            current_menu=ats_tag,
            navigation_history=navigation_history
        )

        # Удаляем предыдущее сообщение с меню
        try:
            await callback_query.message.delete()
        except:
            pass

        # Спрашиваем пользователя, как он хочет искать
        await callback_query.message.answer(
            "Как вы хотите найти сотрудника?",
            reply_markup=search_kb
        )

        # Устанавливаем состояние ожидания выбора типа поиска
        await state.set_state(SearchState.waiting_for_search_type)

        await callback_query.answer()

    except Exception as e:
        logger.error(f"ATS callback error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка открытия справочника", show_alert=True)


# Обработчик выбора "Искать по ФИО"
@router.message(StateFilter(SearchState.waiting_for_search_type), F.text == BTN_EMPLOYEE_SEARCH)
async def handle_name_search(message: Message, state: FSMContext):
    """Обрабатывает выбор поиска по ФИО"""
    try:
        # Убираем клавиатуру выбора
        await message.answer(
            "👤 Введите ФИО сотрудника:",
            reply_markup=ReplyKeyboardRemove()
        )

        # Устанавливаем состояние ожидания ввода ФИО
        await state.set_state(SearchState.waiting_for_name_search)

    except Exception as e:
        logger.error(f"Name search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска по ФИО")


# Обработчик выбора "Искать по отделу"
@router.message(StateFilter(SearchState.waiting_for_search_type), F.text == BTN_DEPARTMENT_SEARCH)
async def handle_department_search(message: Message, state: FSMContext):
    """Обрабатывает выбор поиска по отделу"""
    try:
        # Убираем клавиатуру выбора
        await message.answer(
            "Введите название отдела:",
            reply_markup=ReplyKeyboardRemove()
        )

        # Устанавливаем состояние ожидания ввода отдела
        await state.set_state(SearchState.waiting_for_department_search)

    except Exception as e:
        logger.error(f"Department search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска по отделу")


# Обработчик кнопки "Назад"
@router.message(StateFilter(SearchState.waiting_for_search_type), F.text == BTN_BACK)
async def handle_back_from_search(message: Message, state: FSMContext):
    """Обрабатывает кнопку Назад из режима поиска"""
    try:
        logger.info(f"Обработка кнопки Назад для пользователя {message.from_user.id}")

        # Убираем клавиатуру
        await message.answer(
            "Возвращаемся в главное меню...",
            reply_markup=ReplyKeyboardRemove()
        )

        # Сбрасываем состояние поиска
        await state.clear()
        logger.info("Состояние поиска очищено")

        # Возвращаем в главное меню
        logger.info("Вызов start_navigation...")
        await start_navigation(message=message, state=state)
        logger.info("start_navigation завершен успешно")

    except Exception as e:
        logger.error(f"Back from search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при возврате в меню")


# Обработчик ввода ФИО (заглушка)
@router.message(StateFilter(SearchState.waiting_for_name_search))
async def process_name_input(message: Message, state: FSMContext):
    """Обрабатывает ввод ФИО для поиска"""
    search_query = message.text.strip()
    logger.info(f"Поиск по ФИО: {search_query}")

    # Здесь будет ваша функция поиска по ФИО
    await message.answer(f"🔍 Ищем сотрудника: {search_query}")

    # Сбрасываем состояние
    await state.clear()


# Обработчик ввода отдела (заглушка)
@router.message(StateFilter(SearchState.waiting_for_department_search))
async def process_department_input(message: Message, state: FSMContext):
    """Обрабатывает ввод отдела для поиска"""
    department = message.text.strip()
    logger.info(f"Поиск по отделу: {department}")

    # Здесь будет ваша функция поиска по отделу
    await message.answer(f"🏢 Ищем сотрудников в отделе: {department}")

    # Сбрасываем состояние
    await state.clear()


# Обработчик отмены (если пользователь ввел что-то не то)
@router.message(StateFilter(SearchState.waiting_for_search_type))
async def handle_wrong_search_input(message: Message, state: FSMContext):
    """Обрабатывает некорректный ввод при выборе типа поиска"""
    await message.answer(
        "Пожалуйста, выберите тип поиска с помощью кнопок ниже:",
        reply_markup=search_kb
    )