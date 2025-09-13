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
        logger.info(f"Установлено состояние: {SearchState.waiting_for_search_type}")

        await callback_query.answer()

    except Exception as e:
        logger.error(f"ATS callback error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка открытия справочника", show_alert=True)


# Обработчик выбора "Искать по ФИО"
@router.message(StateFilter(SearchState.waiting_for_search_type), F.text == BTN_EMPLOYEE_SEARCH)
async def handle_name_search(message: Message, state: FSMContext):
    """Обрабатывает выбор поиска по ФИО"""
    try:
        # Убираем клавиатуру выбора и просим ввести ФИО
        await message.answer(
            "Укажите пожалуйста, фамилию и/или полное имя сотрудника, например: Иван Смирнов или Смирнов Иван, "
            "или Смирнов, или просто Иван.",
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
        # Убираем клавиатуру выбора и просим ввести отдел
        await message.answer(
            "Укажите пожалуйста, название отдела.",
            reply_markup=ReplyKeyboardRemove()
        )

        # Устанавливаем состояние ожидания ввода отдела
        await state.set_state(SearchState.waiting_for_department_search)

    except Exception as e:
        logger.error(f"Department search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска по отделу")



# Обработчик кнопки "Назад" из состояния выбора типа поиска
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

        # Возвращаем в главное меню - создаем новое сообщение
        await start_navigation(message=message, state=state)

    except Exception as e:
        logger.error(f"Back from search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при возврате в меню")


# Общий обработчик кнопки "Назад" для состояний ввода
@router.message(
    StateFilter(
        SearchState.waiting_for_name_search,
        SearchState.waiting_for_department_search
    ),
    F.text == BTN_BACK
)
async def handle_back_from_input(message: Message, state: FSMContext):
    """Обрабатывает кнопку Назад во время ввода ФИО или отдела"""
    try:
        # Возвращаем к выбору типа поиска
        await message.answer(
            "Как вы хотите найти сотрудника?",
            reply_markup=search_kb
        )
        await state.set_state(SearchState.waiting_for_search_type)

    except Exception as e:
        logger.error(f"Back from input error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при возврате к выбору поиска")


# Обработчик ввода ФИО
@router.message(StateFilter(SearchState.waiting_for_name_search))
async def process_name_input(message: Message, state: FSMContext):
    """Обрабатывает ввод ФИО для поиска"""
    try:
        search_query = message.text.strip()

        # Если пустой запрос
        if not search_query:
            await message.answer("Пожалуйста, введите ФИО сотрудника:")
            return

        logger.info(f"Поиск по ФИО: {search_query}")

        # Здесь будет ваша функция поиска по ФИО
        # employees = await get_employee_by_name(search_query)

        # Временно: заглушка для тестирования
        await message.answer(f"🔍 Ищем сотрудника: {search_query}")

        # После поиска показываем результаты и кнопку Назад
        # await give_employee_data(message, employees, state)

        # Пока просто возвращаем к выбору типа поиска
        await message.answer(
            "Поиск завершен. Как вы хотите найти сотрудника?",
            reply_markup=search_kb
        )
        await state.set_state(SearchState.waiting_for_search_type)

    except Exception as e:
        logger.error(f"Name input processing error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при обработке запроса")


# Обработчик ввода отдела
@router.message(StateFilter(SearchState.waiting_for_department_search))
async def process_department_input(message: Message, state: FSMContext):
    """Обрабатывает ввод отдела для поиска"""
    try:
        department = message.text.strip()

        # Если пустой запрос
        if not department:
            await message.answer("Пожалуйста, введите название отдела:")
            return

        logger.info(f"Поиск по отделу: {department}")

        # Здесь будет ваша функция поиска по отделу
        # employees = await get_employee_by_department(department)

        # Временно: заглушка для тестирования
        await message.answer(f"🏢 Ищем сотрудников в отделе: {department}")

        # После поиска показываем результаты и кнопку Назад
        # await give_employee_data(message, employees, state)

        # Пока просто возвращаем к выбору типа поиска
        await message.answer(
            "Поиск завершен. Как вы хотите найти сотрудника?",
            reply_markup=search_kb
        )
        await state.set_state(SearchState.waiting_for_search_type)

    except Exception as e:
        logger.error(f"Department input processing error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при обработке запроса")



@router.message()
async def fallback_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.warning(f"[FALLBACK] Необработанное сообщение: {message.text!r} при состоянии {current_state}")
    await message.answer("⚠️ Команда не распознана. Попробуйте ещё раз или нажмите «Назад».")