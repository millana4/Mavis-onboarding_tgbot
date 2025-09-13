from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BTN_SHARE_CONTACT = "☎️ Поделиться контактом"

share_contact_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

BTN_EMPLOYEE_SEARCH = '🔍 Искать по ФИО'
BTN_DEPARTMENT_SEARCH = '👀 Искать по отделу'
BTN_BACK = '⬅️ Назад'

search_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_EMPLOYEE_SEARCH), KeyboardButton(text=BTN_DEPARTMENT_SEARCH)],
        [KeyboardButton(text=BTN_BACK)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)