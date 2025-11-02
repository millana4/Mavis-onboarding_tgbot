import re
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from typing import List, Dict

from app.services.cache_access import check_user_access, RESTRICTING_MESSAGE
from config import Config
from telegram.handlers.handler_base import start_navigation
from telegram.keyboards import search_kb, BTN_DEPARTMENT_SEARCH, BTN_EMPLOYEE_SEARCH, BTN_BACK
from app.seatable_api.api_ats import get_employees, get_department_list

router = Router()
logger = logging.getLogger(__name__)


# Хендлер для кнопки со справочником сотрудников
@router.callback_query(lambda c: c.data.startswith('ats:'))
async def process_ats_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие на кнопку со справочником"""
    try:
        # Проверяем права доступа
        if not await check_user_access(callback_query.from_user.id):
            await callback_query.answer(
                RESTRICTING_MESSAGE,
                show_alert=True
            )
            logger.info(f"У пользователя {callback_query.from_user.id} больше нет доступа. Запрещено в process_ats_callback")
            return
        else:
            logger.info(f"Доступ пользователя {callback_query.from_user.id} подтвержден")

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
        # Проверяем права доступа
        if not await check_user_access(message.from_user.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.from_user.id} больше нет доступа. Запрещено в handle_name_search")
            return
        else:
            logger.info(f"Доступ пользователя {message.from_user.id} подтвержден")

        # Убираем клавиатуру выбора и просим ввести ФИО
        await message.answer(
            "Укажите, пожалуйста, фамилию и/или полное имя сотрудника, например: Иван Соколов или Соколов Иван, "
            "или Соколов, или просто Иван.",
            reply_markup=ReplyKeyboardRemove()
        )

        # Устанавливаем состояние ожидания ввода ФИО
        await state.set_state(SearchState.waiting_for_name_search)

    except Exception as e:
        logger.error(f"Name search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска по ФИО")


# Обработчик ввода ФИО
@router.message(StateFilter(SearchState.waiting_for_name_search))
async def process_name_input(message: Message, state: FSMContext):
    """Обрабатывает ввод ФИО для поиска"""
    try:
        # Проверяем права доступа
        if not await check_user_access(message.from_user.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.from_user.id} больше нет доступа. Запрещено в process_name_input")
            return
        else:
            logger.info(f"Доступ пользователя {message.from_user.id} подтвержден")

        search_query = message.text.strip()

        # Если пустой запрос
        if not search_query:
            await message.answer("Пожалуйста, введите ФИО сотрудника:")
            return

        logger.info(f"Поиск по ФИО: {search_query}")

        # Обращается по АПИ в таблицу со справочником и возвращает json с данными всех сотрудников
        employees = await get_employees()

        # После поиска показываем результаты и кнопку Назад
        searched_employees = await give_employee_data("Name/Department", search_query, employees, state)

        # Выводит сообщение с результатами поиска и показывает его, пока пользователь не нажмет Назад
        await show_employee(searched_employees, message, state)

    except Exception as e:
        logger.error(f"Name input processing error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при обработке запроса")


async def give_employee_data(search_type: str, search_query: str, employees: List[Dict], state: FSMContext) -> List[Dict]:
    """
    Ищет сотрудников по строке search_query в списке employees.
    На вход нужно передать тип поиска:
    - По ФИО: "Name/Department"
    - По отделу: "Department"
    Возвращает список с данными найденных сотрудников.
    """
    results = []
    if not employees:
        return results

    # Нормализуем запрос
    query = search_query.strip().lower()
    query_words = re.split(r"\s+", query)

    for emp in employees:
        # Берём ФИО/отдел, если оно есть
        name_field = emp.get(search_type, "")
        if not name_field:
            continue

        name_norm = name_field.lower()

        # --- Одинарный запрос (только имя или фамилия)
        if len(query_words) == 1:
            if query_words[0] in name_norm:
                results.append(emp)

        # --- Два слова (имя + фамилия в любом порядке)
        elif len(query_words) >= 2:
            w1, w2 = query_words[0], query_words[1]
            if f"{w1} {w2}" in name_norm or f"{w2} {w1}" in name_norm:
                results.append(emp)

    logger.info(f"По запросу '{search_query}' найдено {len(results)} сотрудник(ов)")
    await state.update_data(search_results=results)
    return results


async def show_employee(searched_employees: List[Dict], message: Message, state: FSMContext):
    """
    Формирует сообщение с результатами поиска сотрудников и выводит его в чат.
    """
    # Если ничего не нашли
    if not searched_employees:
        await message.answer(
            "К сожалению, ничего не нашли. Отправьте, пожалуйста, другой запрос.",
            reply_markup=search_kb
        )
        await state.set_state(SearchState.waiting_for_search_type)
        return

    text_blocks = []

    # Если один результат и есть фото
    if len(searched_employees) == 1:
        emp = searched_employees[0]
        photo_urls = emp.get("Photo", [])
        text = format_employee_text(emp)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="search_back")]]
        )

        if photo_urls:
            await message.answer_photo(
                photo=photo_urls[0],
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

    else:
        # Несколько сотрудников — фото не показываем
        for emp in searched_employees:
            text_blocks.append(format_employee_text(emp))

        full_text = "\n\n".join(text_blocks)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="search_back")]]
        )

        await message.answer(
            full_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


def format_employee_text(emp: Dict) -> str:
    """
    Форматирует данные одного сотрудника в текст.
    """
    parts = []

    # Имя жирным
    if emp.get("Name/Department"):
        parts.append(f"<b>{emp['Name/Department']}</b>")

    if emp.get("Number"):
        parts.append(f"Телефон: {emp['Number']}")

    if emp.get("Email"):
        parts.append(f"Email: {emp['Email']}")

    if emp.get("Location"):
        parts.append(f"Рабочее место: {emp['Location']}")

    if emp.get("Position"):
        parts.append(f"Должность: {emp['Position']}")

    if emp.get("Department"):
        parts.append(f"Отдел: {emp['Department']}")

    if emp.get("Company"):
        company_val = emp["Company"]
        if isinstance(company_val, list):
            company_val = ", ".join(company_val)
        parts.append(f"Компания: {company_val}")

    return "\n".join(parts)


# Обработчик выбора "Искать по отделу"
@router.message(StateFilter(SearchState.waiting_for_search_type), F.text == BTN_DEPARTMENT_SEARCH)
async def handle_department_search(message: types.Message, state: FSMContext):
    """Обрабатывает выбор поиска по отделу"""
    try:
        # Проверяем права доступа
        if not await check_user_access(message.from_user.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.from_user.id} больше нет доступа. Запрещено в handle_department_search")
            return
        else:
            logger.info(f"Доступ пользователя {message.from_user.id} подтвержден")

        # Убираем клавиатуру выбора (ReplyKeyboard) и просим выбрать отдел
        await message.answer(
            "Выберите, пожалуйста, отдел ⬇️",
            reply_markup=ReplyKeyboardRemove()
        )

        # Создаём инлайн-клавиатуру с отделами
        keyboard = await _create_department_keyboard()

        # Устанавливаем состояние ожидания ввода отдела
        await state.set_state(SearchState.waiting_for_department_search)

        # Отправляем инлайн-клавиатуру пользователю
        await message.answer("Список отделов:", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Department search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска телефонов по отделу")


async def _create_department_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком доступных отделов, по которым можно получить телефоны.
    Кнопки выводятся по 2 в строку.
    """
    # Получаем из справочника список отделов
    department_list = await get_department_list()

    inline_keyboard = []

    # Группируем по 2 кнопки в ряд
    row = []
    for i, department in enumerate(department_list, start=1):
        row.append(InlineKeyboardButton(
            text=department,
            callback_data=f"department:{department}"
        ))
        if i % 2 == 0:  # каждые 2 кнопки — новая строка
            inline_keyboard.append(row)
            row = []

    # если осталось "хвостиком" одна кнопка — добавляем её в отдельной строке
    if row:
        inline_keyboard.append(row)

    # Добавляем кнопку "Назад"
    inline_keyboard.append([InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back"
    )])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# Обработчик ввода отдела
@router.callback_query(lambda c: c.data.startswith('department:'))
async def process_department_input(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает ввод отдела для поиска"""
    try:
        # Проверяем права доступа
        if not await check_user_access(callback_query.from_user.id):
            await callback_query.answer(
                RESTRICTING_MESSAGE,
                show_alert=True
            )
            logger.info(f"У пользователя {callback_query.from_user.id} больше нет доступа. Запрещено в process_department_input")
            return
        else:
            logger.info(f"Доступ пользователя {callback_query.from_user.id} подтвержден")

        # Убираем "часики" на кнопке
        await callback_query.answer()

        # Извлекаем выбранное значение (без префикса department:)
        search_query = callback_query.data.replace("department:", "")
        logger.info(f"Поиск телефонов по отделу: {search_query}")

        # Убираем инлайн-клавиатуру с отделами
        await callback_query.message.edit_reply_markup(reply_markup=None)

        # Получаем данные сотрудников
        employees = await get_employees()

        # Фильтруем по отделу
        searched_employees = await give_employee_data("Department", search_query, employees, state)

        # Показываем результат поиска
        await show_employee(searched_employees, callback_query.message, state)

    except Exception as e:
        logger.error(f"Department input processing error: {str(e)}", exc_info=True)
        await callback_query.message.answer("Ошибка при обработке запроса телефонов отдела")


# Обработчик кнопки "Назад" из состояния выбора типа поиска
@router.message(StateFilter(SearchState.waiting_for_search_type), F.text == BTN_BACK)
async def handle_back_from_search(message: Message, state: FSMContext):
    """Обрабатывает кнопку Назад из режима поиска"""
    try:
        # Проверяем права доступа
        if not await check_user_access(message.chat.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.chat.id} больше нет доступа. Запрещено в handle_back_from_search")
            return
        else:
            logger.info(f"Доступ пользователя {message.chat.id} подтвержден")

        logger.info(f"Обработка кнопки Назад для пользователя {message.chat.id}")

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


@router.callback_query(F.data == "search_back")
async def handle_search_back(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает кнопку Назад из результатов поиска — возвращает в главное меню"""
    try:
        # Проверяем права доступа
        if not await check_user_access(callback.from_user.id):
            await callback.answer(
                RESTRICTING_MESSAGE,
                show_alert=True
            )
            logger.info(f"У пользователя {callback.from_user.id} больше нет доступа. Запрещено в handle_search_back")
            return
        else:
            logger.info(f"Доступ пользователя {callback.from_user.id} подтвержден")

        logger.info(f"Обработка кнопки Назад (inline) для пользователя {callback.from_user.id}")

        # Удаляем сообщение с результатами
        try:
            await callback.message.delete()
        except:
            pass

        # Убираем состояние поиска
        await state.clear()
        logger.info("Состояние поиска очищено (inline back)")

        # Сообщаем пользователю
        await callback.message.answer(
            "Назад в главное меню...",
            reply_markup=ReplyKeyboardRemove()
        )

        # Запускаем главное меню
        await start_navigation(message=callback.message, state=state)

        await callback.answer()

    except Exception as e:
        logger.error(f"Search back (inline) error: {str(e)}", exc_info=True)
        await callback.answer("Ошибка при возврате в меню", show_alert=True)


@router.message(StateFilter(None))
async def fallback_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.warning(f"[FALLBACK] Необработанное сообщение: {message.text!r} при состоянии {current_state}")
    await message.answer("⚠️ Команда не распознана. Попробуйте ещё раз или нажмите «Назад».")