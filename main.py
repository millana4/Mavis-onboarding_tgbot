import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import custom_logging
import handlers
from config import Config

# Инициализация логирования
custom_logging.setup_logging()
logger = logging.getLogger(__name__)

async def main():
    logger.info("Запуск бота...")

    # Инициализация хранилища MemoryStorage
    storage = MemoryStorage()
    logger.info("Используется MemoryStorage")

    # Инициализация бота и диспетчера
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Регистрация роутеров
    dp.include_router(handlers.router)

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())