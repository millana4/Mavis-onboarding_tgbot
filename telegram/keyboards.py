from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

BTN_SHARE_CONTACT = "☎️ Поделиться контактом"

share_contact_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# Клавиатура для выбора типа поиска в справочнике сотрудников
SEARCH_TYPE_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Искать по ФИО", callback_data="search_by_name")],
    [InlineKeyboardButton(text="Искать по отделу", callback_data="search_by_department")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])