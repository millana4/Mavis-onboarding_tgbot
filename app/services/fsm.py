from cachetools import TTLCache
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AppStates:
    CURRENT_MENU = "current_menu"
    FORM_DATA = "form_data"
    WAITING_FOR_SEARCH_TYPE = "waiting_for_search_type"
    WAITING_FOR_NAME_SEARCH = "waiting_for_name_search"
    WAITING_FOR_DEPARTMENT_SEARCH = "waiting_for_department_search"


class StateManager:
    def __init__(self, maxsize=1000, ttl=3600):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    async def set_state(self, user_id: int, state: str, data: Dict[str, Any] = None):
        user_data = self._cache.get(user_id, {})
        user_data['current_state'] = state
        if data:
            user_data.update(data)

        self._cache[user_id] = user_data
        logger.debug(f"User {user_id} state set to: {state}")

    async def get_state(self, user_id: int) -> Optional[str]:
        user_data = self._cache.get(user_id, {})
        return user_data.get('current_state')

    async def get_data(self, user_id: int) -> Dict[str, Any]:
        return self._cache.get(user_id, {}).copy()

    async def update_data(self, user_id: int, **kwargs):
        user_data = self._cache.get(user_id, {})
        user_data.update(kwargs)
        self._cache[user_id] = user_data

    async def clear(self, user_id: int):
        if user_id in self._cache:
            del self._cache[user_id]


# Глобальный экземпляр
state_manager = StateManager()