import logging
import pprint
from typing import List, Dict

from aiogram import Router, types, F
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.fsm import state_manager, AppStates
from app.services.ats import give_employee_data, format_employee_text
from app.seatable_api.api_ats import get_employees, get_department_list

from telegram.handlers.handler_base import start_navigation
from telegram.handlers.filters import NameSearchFilter
from telegram.keyboards import search_kb, BTN_DEPARTMENT_SEARCH, BTN_EMPLOYEE_SEARCH, BTN_BACK
from telegram.utils import check_access


router = Router()
logger = logging.getLogger(__name__)


# Хендлер для кнопки со справочником сотрудников
@router.callback_query(lambda c: c.data.startswith('ats:'))
async def process_ats_callback(callback_query: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку со справочником"""
    try:
        user_id = callback_query.from_user.id

        # Проверяем права доступа
        await check_access(callback_query=callback_query)

        # Получаем и обновляем состояние
        ats_tag = callback_query.data.split(':')[1]
        await state_manager.navigate_to_menu(user_id, ats_tag)

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
        await state_manager.update_data(user_id, current_state=AppStates.WAITING_FOR_SEARCH_TYPE)
        logger.info(f"Установлено состояние: {AppStates.WAITING_FOR_SEARCH_TYPE}")

        await callback_query.answer()

    except Exception as e:
        logger.error(f"ATS callback error: {str(e)}", exc_info=True)
        await callback_query.answer("Ошибка открытия справочника", show_alert=True)


# Обработчик выбора "Искать по ФИО"
@router.message(F.text == BTN_EMPLOYEE_SEARCH)
async def handle_name_search(message: Message):
    """Обрабатывает выбор поиска по ФИО"""
    try:
        user_id = message.from_user.id

        # Проверяем права доступа
        await check_access(message=message)

        # Проверяем, что пользователь в правильном состоянии
        user_data = await state_manager.get_data(user_id)
        if user_data.get('current_state') != AppStates.WAITING_FOR_SEARCH_TYPE:
            return

        # Убираем клавиатуру выбора и просим ввести ФИО
        await message.answer(
            "Укажите, пожалуйста, фамилию и/или полное имя сотрудника, например: Иван Соколов или Соколов Иван, "
            "или Соколов, или просто Иван.",
            reply_markup=ReplyKeyboardRemove()
        )

        # Устанавливаем состояние ожидания ввода ФИО
        await state_manager.update_data(user_id, current_state=AppStates.WAITING_FOR_NAME_SEARCH)
        logger.info(f"Установлено состояние: {AppStates.WAITING_FOR_NAME_SEARCH}")

    except Exception as e:
        logger.error(f"Name search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска по ФИО")


# Обработчик ввода ФИО
@router.message(F.text, F.content_type == 'text', NameSearchFilter())
async def process_name_input(message: Message):
    """Обрабатывает ввод ФИО для поиска"""
    try:
        user_id = message.from_user.id

        # Проверяем права доступа
        await check_access(message=message)

        # Проверяем, что пользователь в правильном состоянии
        user_data = await state_manager.get_data(user_id)
        if user_data.get('current_state') != AppStates.WAITING_FOR_NAME_SEARCH:
            return

        search_query = message.text.strip()

        # Если пустой запрос
        if not search_query:
            await message.answer("Пожалуйста, введите ФИО сотрудника:")
            return

        logger.info(f"Поиск по ФИО: {search_query}")

        # Обращается по АПИ в таблицу со справочником и возвращает json с данными всех сотрудников
        employees = await get_employees()

        # После поиска показываем результаты и кнопку Назад
        searched_employees = await give_employee_data("Name/Department", search_query, employees)

        # Выводит сообщение с результатами поиска и показывает его, пока пользователь не нажмет Назад
        await show_employee(searched_employees, message)

    except Exception as e:
        logger.error(f"Name input processing error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при обработке запроса")


async def show_employee(searched_employees: List[Dict], message: Message):
    """
    Формирует сообщение с результатами поиска сотрудников и выводит его в чат.
    """
    user_id = message.from_user.id

    # Если ничего не нашли
    if not searched_employees:
        await message.answer(
            "К сожалению, ничего не нашли. Отправьте, пожалуйста, другой запрос.",
            reply_markup=search_kb
        )
        await state_manager.update_data(user_id, current_state=AppStates.WAITING_FOR_SEARCH_TYPE)
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


# Обработчик выбора "Искать по отделу"
@router.message(F.text == BTN_DEPARTMENT_SEARCH)
async def handle_department_search(message: types.Message):
    """Обрабатывает выбор поиска по отделу"""
    try:
        user_id = message.from_user.id

        # Проверяем права доступа
        await check_access(message=message)

        user_data = await state_manager.get_data(user_id)
        if user_data.get('current_state') != AppStates.WAITING_FOR_SEARCH_TYPE:
            return

        # Убираем клавиатуру выбора (ReplyKeyboard) и просим выбрать отдел
        await message.answer(
            "Выберите, пожалуйста, отдел ⬇️",
            reply_markup=ReplyKeyboardRemove()
        )

        # Создаём инлайн-клавиатуру с отделами
        keyboard = await create_department_keyboard()

        # Устанавливаем состояние ожидания ввода отдела
        await state_manager.update_data(user_id, current_state=AppStates.WAITING_FOR_DEPARTMENT_SEARCH)
        logger.info(f"Установлено состояние: {AppStates.WAITING_FOR_DEPARTMENT_SEARCH}")

        # Отправляем инлайн-клавиатуру пользователю
        await message.answer("Список отделов:", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Department search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при выборе поиска телефонов по отделу")


async def create_department_keyboard() -> InlineKeyboardMarkup:
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
async def process_department_input(callback_query: types.CallbackQuery):
    """Обрабатывает ввод отдела для поиска"""
    try:
        user_id = callback_query.from_user.id

        # Проверяем права доступа
        await check_access(callback_query=callback_query)

        # Проверяем, что пользователь в правильном состоянии
        user_data = await state_manager.get_data(user_id)
        if user_data.get('current_state') != AppStates.WAITING_FOR_DEPARTMENT_SEARCH:
            return

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
        searched_employees = await give_employee_data("Department", search_query, employees)

        # Показываем результат поиска
        await show_employee(searched_employees, callback_query.message)

    except Exception as e:
        logger.error(f"Department input processing error: {str(e)}", exc_info=True)
        await callback_query.message.answer("Ошибка при обработке запроса телефонов отдела")


# Обработчик кнопки "Назад" из состояния выбора типа поиска
@router.message(F.text == BTN_BACK)
async def handle_back_from_search(message: Message):
    """Обрабатывает кнопку Назад из режима поиска"""
    try:
        user_id = message.chat.id

        # Проверяем права доступа
        await check_access(message=message)

        logger.info(f"Обработка кнопки Назад для пользователя {message.chat.id}")

        # Проверяем, что пользователь в правильном состоянии
        user_data = await state_manager.get_data(user_id)
        if user_data.get('current_state') != AppStates.WAITING_FOR_SEARCH_TYPE:
            return

        # Убираем клавиатуру
        await message.answer(
            "Возвращаемся в главное меню...",
            reply_markup=ReplyKeyboardRemove()
        )

        # Сбрасываем состояние поиска
        await state_manager.clear(user_id)
        logger.info("Состояние поиска очищено")

        # Возвращаем в главное меню - создаем новое сообщение
        await start_navigation(message=message)

    except Exception as e:
        logger.error(f"Back from search error: {str(e)}", exc_info=True)
        await message.answer("Ошибка при возврате в меню")


@router.callback_query(F.data == "search_back")
async def handle_search_back(callback: types.CallbackQuery):
    """Обрабатывает кнопку Назад из результатов поиска — возвращает в главное меню"""
    try:
        user_id = callback.from_user.id

        # Проверяем права доступа
        await check_access(callback_query=callback)

        # Удаляем сообщение с результатами
        try:
            await callback.message.delete()
        except:
            pass

        # Убираем состояние поиска
        await state_manager.clear(user_id)
        logger.info("Состояние поиска очищено (inline back)")

        # Сообщаем пользователю
        await callback.message.answer(
            "Назад в главное меню...",
            reply_markup=ReplyKeyboardRemove()
        )

        # Запускаем главное меню
        await start_navigation(message=callback.message)

        await callback.answer()

    except Exception as e:
        logger.error(f"Search back (inline) error: {str(e)}", exc_info=True)
        await callback.answer("Ошибка при возврате в меню", show_alert=True)
