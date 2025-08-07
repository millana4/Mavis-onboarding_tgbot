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

logger.info("Настройка логирования завершена")

async def main():

    # 2. Инициализация бота и диспетчера
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Регистрация хендлеров
    dp.include_router(handlers.router)

    # 4. Запуск бота (современный асинхронный способ)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())