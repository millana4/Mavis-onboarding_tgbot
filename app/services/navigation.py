import logging
from typing import List, Dict

from telegram.utils import prepare_telegram_message


logger = logging.getLogger(__name__)


async def process_content_part(table_data: List[Dict]) -> Dict:
    """Обрабатывает контентную часть (Info)"""
    logger.info("Поиск контентной части (Info) в данных таблицы")

    for row in table_data:
        if row.get('Name') == 'Info' and row.get('Content'):
            logger.info("Найдена строка с контентом (Info)")
            return prepare_telegram_message(row['Content'])

    logger.info("Строка с контентом (Info) не найдена")
    return {"text": ""}