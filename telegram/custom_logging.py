import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from aiogram.types import Update


class UserLoggingMiddleware:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        if event.message:
            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id

        if user_id:
            self.logger.info(f"Update id={event.update_id}", extra={'user_id': user_id})
        else:
            self.logger.info(f"Update id={event.update_id} (no user_id)")

        return await handler(event, data)


class UserIdFilter(logging.Filter):
    """Фильтр для добавления ID пользователя в логи"""
    def filter(self, record):
        if hasattr(record, 'user_id'):
            if record.msg.startswith(f"[user:{record.user_id}]"):
                return True
            record.msg = f"[user:{record.user_id}] {record.msg}"
        return True

def setup_logging():
    """Настройка логирования для всего проекта"""
    # Создаем папку для логов
    log_dir = Path("../logs")
    log_dir.mkdir(exist_ok=True)

    # Основные настройки
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Наш кастомный фильтр
    user_filter = UserIdFilter()

    # Файловый обработчик
    file_handler = RotatingFileHandler(
        '../logs/bot.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(user_filter)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(user_filter)

    # Добавляем обработчики
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    # Настройка логирования aiogram
    aiogram_logger = logging.getLogger('aiogram')
    aiogram_logger.setLevel(logging.INFO)