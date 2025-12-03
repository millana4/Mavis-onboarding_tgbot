import asyncio
import logging
from datetime import datetime, time, timedelta
from app.services.process_1c import (
    get_unprocessed_1c_users,
    user_exists_in_users_table,
    create_user_in_users_table,
    update_user_in_users_table,
    mark_user_as_processed
)

logger = logging.getLogger(__name__)

# Время синхронизации выгрузки 1С и авторизационной таблицы
sync_times = [time(12, 00), time(16, 0)]


async def sync_1c_to_users():
    """
    Основная функция синхронизации
    """
    logger.info("Синхронизация 1С начата")

    # Получаем необработанных пользователей из 1С
    unprocessed_users = await get_unprocessed_1c_users()

    if not unprocessed_users:
        logger.info("Нет необработанных пользователей")
        return

    success_count = 0

    # Обрабатываем каждого пользователя
    for user in unprocessed_users:
        try:
            # Проверяем, существует ли пользователь уже в таблице пользователей
            exists, row_id = await user_exists_in_users_table(user.snils)

            if exists:
                # Обновляем существующего пользователя
                success = await update_user_in_users_table(user, row_id)
            else:
                # Создаем нового пользователя
                success = await create_user_in_users_table(user)

            # Если операция успешна - помечаем как обработанного
            if success:
                await mark_user_as_processed(user)
                success_count += 1

        except Exception as e:
            logger.error(f"Ошибка обработки {user.fio}: {str(e)}")

    logger.info(f"Синхронизация завершена. Обработано: {success_count}/{len(unprocessed_users)}")


async def start_sync_scheduler():
    """
    Запускает планировщик синхронизации
    """
    logger.info("Планировщик синхронизации с 1С запущен")

    while True:
        for sync_time in sync_times:
            # Ждем до времени запуска
            await _wait_until(sync_time)

            # Запускаем синхронизацию
            try:
                await sync_1c_to_users()
            except Exception as e:
                logger.error(f"Ошибка синхронизации с 1С: {e}")


async def _wait_until(target_time: time):
    """
    Ждет до указанного времени по Москве
    """
    now_utc = datetime.utcnow()
    moscow_offset = timedelta(hours=3)
    now_msk = now_utc + moscow_offset

    next_run = datetime.combine(now_msk.date(), target_time)

    if next_run < now_msk:
        next_run = next_run + timedelta(days=1)

    wait_seconds = (next_run - now_msk).total_seconds()

    logger.info(f"Следующая синхронизация {target_time.strftime('%H:%M')} МСК")

    await asyncio.sleep(wait_seconds)