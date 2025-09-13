from aiogram.fsm.state import State, StatesGroup

# Состояние для навигации по меню
class Navigation(StatesGroup):
    current_menu = State()  # Хранит текущее меню и историю для каждого пользователя
    form_data = State()  # Состояние для формы

# Состояние для поиска по телефонному справочнику
class SearchState(StatesGroup):
    waiting_for_search_type = State()
    waiting_for_name_search = State()
    waiting_for_department_search = State()