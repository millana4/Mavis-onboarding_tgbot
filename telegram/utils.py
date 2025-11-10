import pprint
import re
import html
import logging
from typing import Dict

from aiogram import types
from aiogram.client.session import aiohttp
from aiogram.types import ReplyKeyboardRemove

from app.services.cache_access import check_user_cache, RESTRICTING_MESSAGE

logger = logging.getLogger(__name__)


async def check_access (message: types.Message = None, callback_query: types.CallbackQuery = None) -> bool:
    """Функция отвечает, если ли доступ у пользователя. Если нет, выводит сообщение
    :rtype: None
    """
    if callback_query:
        if not await check_user_cache(callback_query.from_user.id):
            await callback_query.answer(
                RESTRICTING_MESSAGE,
                show_alert=True
            )
            logger.info(f"У пользователя {callback_query.from_user.id} больше нет доступа.")
            return False
        else:
            logger.info(f"Доступ пользователя {callback_query.from_user.id} подтвержден")
            return True
    elif message:
        if not await check_user_cache(message.chat.id):
            await message.answer(
                RESTRICTING_MESSAGE,
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"У пользователя {message.chat.id} больше нет доступа.")
            return False
        else:
            logger.info(f"Доступ пользователя {message.chat.id} подтвержден")
            return True
    else:
        False


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


def prepare_telegram_message(markdown_content: str) -> Dict[str, str]:
    """
    Подготавливает контент для отправки в Telegram с HTML разметкой.
    Обрабатывает только первое изображение, остальные медиа-файлы игнорируются.
    """
    if not markdown_content:
        return {'text': ''}

    result = {
        'text': markdown_content,
        'image_url': None,
        'parse_mode': 'HTML'
    }

    # Извлекаем первое медиа
    media_match = re.search(
        r'!\[[^\]]*\]\(([^)]+)\)',
        markdown_content
    )

    if media_match:
        media_url = media_match.group(1).strip()
        result['image_url'] = media_url

        # Удаляем markdown изображения из текста
        markdown_content = markdown_content.replace(media_match.group(0), '', 1).strip()

    # Преобразуем Markdown в HTML
    text = markdown_content

    # Обрабатываем переносы строк
    def replace_newlines(match):
        n = len(match.group(0)) // 2
        return '\n' * n

    text = re.sub(r'\n{2,}', replace_newlines, text)

    # Заголовки (#) -> <b>
    text = re.sub(r'^#+\s*(.+?)\s*$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Жирный текст
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Курсив
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

    # Ссылки
    text = re.sub(r'\[([^\]]+)]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Маркированные списки
    text = re.sub(r'^\*\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

    # Экранируем HTML-сущности
    text = html.escape(text)

    # Восстанавливаем теги
    replacements = {
        '&lt;b&gt;': '<b>',
        '&lt;/b&gt;': '</b>',
        '&lt;i&gt;': '<i>',
        '&lt;/i&gt;': '</i>',
        '&lt;a href=&quot;': '<a href="',
        '&quot;&gt;': '">',
        '&lt;/a&gt;': '</a>'
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    result['text'] = text.strip()
    return result