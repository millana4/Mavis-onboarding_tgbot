import re
from typing import Dict
import html


def prepare_telegram_message(markdown_content: str) -> Dict[str, str]:
    """
    Подготавливает контент для отправки в Telegram с HTML разметкой
    """
    if not markdown_content:
        return {'text': ''}

    result = {
        'text': markdown_content,
        'image_url': None,
        'video_url': None,
        'parse_mode': 'HTML'
    }

    # 1. Извлекаем медиа
    media_match = re.search(
        r'!\[.*?]\((.*?\.(?:png|jpg|jpeg|gif|mp4|mov))\)',
        markdown_content,
        re.IGNORECASE
    )

    if media_match:
        media_url = media_match.group(1)
        if any(ext in media_url.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif']):
            result['image_url'] = media_url
        else:
            result['video_url'] = media_url
        markdown_content = markdown_content.replace(media_match.group(0), '').strip()

    # 2. Преобразуем Markdown в HTML
    text = markdown_content

    # Обрабатываем переносы строк (2\n → 1\n, 4\n → 2\n и т.д.)
    def replace_newlines(match):
        n = len(match.group(0)) // 2  # Сколько пар \n было
        return '\n' * n

    text = re.sub(r'\n{2,}', replace_newlines, text)

    # Заголовки (#) -> <b>
    text = re.sub(r'^#+\s*(.+?)\s*$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Жирный текст
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # Курсив
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)

    # Ссылки
    text = re.sub(r'\[([^\]]+)]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Обрабатываем маркированные списки (* элемент -> • элемент)
    text = re.sub(
        r'^\*\s+(.+)$',
        r'• \1',
        text,
        flags=re.MULTILINE
    )

    # Экранируем HTML-сущности
    text = html.escape(text)

    # Восстанавливаем наши теги после экранирования
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

    # Убираем лишние переносы в начале и конце
    text = text.strip('\n')

    result['text'] = text
    return result
