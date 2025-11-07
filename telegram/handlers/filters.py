from aiogram.filters import Filter
from aiogram import types


class FormFilter(Filter):
    def __init__(self, state: str):
        self.state = state

    async def __call__(self, message: types.Message) -> bool:  # Убрали state_manager из параметров
        from app.services.fsm import state_manager  # Импортируем внутри функции
        data = await state_manager.get_data(message.from_user.id)
        return data.get('current_state') == self.state


class NameSearchFilter(Filter):
    async def __call__(self, message: types.Message) -> bool:
        from app.services.fsm import state_manager, AppStates
        user_data = await state_manager.get_data(message.from_user.id)
        return user_data.get('current_state') == AppStates.WAITING_FOR_NAME_SEARCH