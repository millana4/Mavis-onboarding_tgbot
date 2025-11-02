from cachetools import TTLCache
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self, maxsize=1000, ttl=3600):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)


    async def update_data(self, user_id: int, **kwargs):
        """Основной метод для обновления любых данных пользователя"""
        user_data = self._cache.get(user_id, {})
        user_data.update(kwargs)
        self._cache[user_id] = user_data
        logger.info(f"User {user_id} data updated: {list(kwargs.keys())}")


    async def get_data(self, user_id: int) -> Dict[str, Any]:
        """Получить все данные пользователя"""
        return self._cache.get(user_id, {}).copy()


    async def clear(self, user_id: int):
        """Очистить данные пользователя"""
        if user_id in self._cache:
            del self._cache[user_id]


    # Методы для навигации (специализированные методы)
    async def navigate_to_menu(self, user_id: int, menu_id: str):
        """Переход в новое меню - добавляем в историю"""
        user_data = self._cache.get(user_id, {})

        # Инициализируем историю если её нет
        if 'navigation_history' not in user_data:
            user_data['navigation_history'] = []

        # Добавляем текущее меню в историю
        if 'current_menu' in user_data:
            user_data['navigation_history'].append(user_data['current_menu'])

        # Устанавливаем новое меню
        user_data['current_menu'] = menu_id
        self._cache[user_id] = user_data

        logger.info(f"User {user_id} navigated to menu: {menu_id}")


    async def navigate_back(self, user_id: int) -> Optional[str]:
        """Возврат к предыдущему меню"""
        user_data = self._cache.get(user_id, {})

        if not user_data.get('navigation_history'):
            logger.debug(f"No navigation history for user {user_id}")
            return None

        # Получаем предыдущее меню из истории
        previous_menu = user_data['navigation_history'].pop()
        user_data['current_menu'] = previous_menu
        self._cache[user_id] = user_data

        logger.debug(f"User {user_id} navigated back to: {previous_menu}")
        return previous_menu

    async def get_current_menu(self, user_id: int) -> Optional[str]:
        """Получить текущее меню пользователя"""
        user_data = self._cache.get(user_id, {})
        return user_data.get('current_menu')

    async def get_navigation_history(self, user_id: int) -> List[str]:
        """Получить историю навигации пользователя"""
        user_data = self._cache.get(user_id, {})
        return user_data.get('navigation_history', []).copy()


# Глобальный экземпляр
state_manager = StateManager()