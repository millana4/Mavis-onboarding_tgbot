import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import custom_logging
import handlers
import handler_ats
import handler_form
import handler_table
from config import Config
from custom_logging import UserLoggingMiddleware

async def main():
    # Инициализация логирования
    custom_logging.setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск бота...")

    # Инициализация хранилища MemoryStorage
    storage = MemoryStorage()
    logger.info("Используется MemoryStorage")

    # Инициализация бота и диспетчера
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Добавляем middleware
    dp.update.middleware(UserLoggingMiddleware())

    # Регистрация роутеров
    dp.include_router(handlers.router)
    dp.include_router(handler_ats.router)
    dp.include_router(handler_form.router)
    dp.include_router(handler_table.router)


    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())