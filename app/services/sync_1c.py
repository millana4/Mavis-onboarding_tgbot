import asyncio
import logging
from datetime import datetime, time, timedelta

from app.services.process_1c import get_unprocessed_1c_users, process_1c_user

logger = logging.getLogger(__name__)

# Времена запуска
sync_times = [time(12, 0), time(16, 0)]

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
            success = await process_1c_user(user)
            if success:
                success_count += 1

        except Exception as e:
            logger.error(f"Ошибка обработки {user.fio}: {str(e)}")

    logger.info(f"Синхронизация с 1С завершена. Обработано: {success_count}/{len(unprocessed_users)}")


async def start_sync_scheduler():
    """
    Запускает планировщик синхронизации
    """
    logger.info("Планировщик синхронизации с 1С запущен")

    while True:
        # Сначала находим ближайшее время из sync_times
        now_utc = datetime.utcnow()
        moscow_offset = timedelta(hours=3)
        now_msk = now_utc + moscow_offset

        # Ищем ближайшее будущее время
        nearest_time = None
        nearest_datetime = None

        for sync_time in sync_times:
            # Время на сегодня
            sync_datetime = datetime.combine(now_msk.date(), sync_time)

            # Если время уже прошло - берем на завтра
            if sync_datetime < now_msk:
                sync_datetime = sync_datetime + timedelta(days=1)

            # Ищем ближайшее
            if nearest_datetime is None or sync_datetime < nearest_datetime:
                nearest_datetime = sync_datetime
                nearest_time = sync_time

        if nearest_time:
            # Ждем до ближайшего времени
            await _wait_until(nearest_time)

            # Запускаем синхронизацию
            try:
                await sync_1c_to_users()
            except Exception as e:
                logger.error(f"Ошибка синхронизации: {e}")

            # Небольшая пауза чтобы избежать мгновенного повторения
            await asyncio.sleep(5)


async def _wait_until(target_time: time):
    """
    Ждет до указанного времени по Москве
    """
    now_utc = datetime.utcnow()
    moscow_offset = timedelta(hours=3)
    now_msk = now_utc + moscow_offset

    # Время запуска сегодня
    next_run = datetime.combine(now_msk.date(), target_time)

    # Исправляем сравнение - используем комбинацию даты и времени
    if next_run < now_msk:
        next_run = next_run + timedelta(days=1)

    wait_seconds = (next_run - now_msk).total_seconds()

    hours = wait_seconds // 3600
    minutes = (wait_seconds % 3600) // 60

    logger.info(f"Ждем синхронизацию с 1С в {target_time.strftime('%H:%M')} МСК")
    logger.info(f"Осталось {int(hours)} часов {int(minutes)} минут")

    await asyncio.sleep(wait_seconds)