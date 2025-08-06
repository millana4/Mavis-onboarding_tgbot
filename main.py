import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import custom_logging

custom_logging.setup_logging()
logger = logging.getLogger(__name__)

logger.info("Настройка логирования завершена")


async def main():
    dp = Dispatcher(storage=MemoryStorage())

if __name__ == "__main__":
    asyncio.run(main())