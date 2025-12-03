import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import Config
from app.services.sync_1c import start_sync_scheduler

from telegram import custom_logging
from telegram.bot_menu import set_main_menu
from telegram.handlers import handler_ats, handler_form, handler_table, handler_base, handler_broadcast, handler_checkout_roles, \
    handler_bc_schedule


async def main():
    # Инициализация логирования
    custom_logging.setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск бота...")

    # Планировщик синхронизации бота с данными пользователей из 1С
    scheduler_task = asyncio.create_task(start_sync_scheduler())

    # Инициализация бота и диспетчера
    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(handler_checkout_roles.router)
    dp.include_router(handler_broadcast.router)
    dp.include_router(handler_bc_schedule.router)
    dp.include_router(handler_base.router)
    dp.include_router(handler_ats.router)
    dp.include_router(handler_form.router)
    dp.include_router(handler_table.router)
    dp.startup.register(set_main_menu)

    # Запуск бота
    try:
        await dp.start_polling(bot)
    finally:
        # Отменяем задачу планировщика
        scheduler_task.cancel()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())