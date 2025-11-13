import asyncio
import logging
from aiogram import Bot, Dispatcher

from telegram import custom_logging
from telegram.handlers import handler_ats, handler_form, handler_table, handler_base, handler_broadcast
from config import Config

async def main():
    # Инициализация логирования
    custom_logging.setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск бота...")

    # Инициализация бота и диспетчера
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(handler_broadcast.router)
    dp.include_router(handler_base.router)
    dp.include_router(handler_ats.router)
    dp.include_router(handler_form.router)
    dp.include_router(handler_table.router)


    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())