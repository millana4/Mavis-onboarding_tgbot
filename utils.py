import re
import html
import logging
from typing import Dict
from aiogram import types
from aiogram.client.session import aiohttp

logger = logging.getLogger(__name__)


async def download_and_send_file(file_url: str, callback_query: types.CallbackQuery):
    """Скачивает файл по прямому URL и отправляет его в чат, откуда пришёл callback."""
    try:
        # Если ссылка на GitHub blob — заменяем на raw
        if "github.com" in file_url and "/blob/" in file_url:
            file_url = file_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                response.raise_for_status()
                file_data = await response.read()

                file_name = file_url.split("/")[-1]
                file_to_send = types.BufferedInputFile(file_data, filename=file_name)

                await callback_query.message.answer_document(file_to_send)
                logger.info(f"Файл {file_name} отправлен в чат {callback_query.message.chat.id}")

    except Exception as e:
        logger.error(f"Ошибка при скачивании или отправке файла: {str(e)}", exc_info=True)
        await callback_query.message.answer("Не удалось отправить файл. Пожалуйста, попробуйте позже.")


def normalize_phone(raw: str | None) -> str | None:
    """Приводит телефон к формату +7XXXXXXXXXX или возвращает None."""
    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)

    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "7":
        pass
    else:
        return None

    return f"+{digits}"