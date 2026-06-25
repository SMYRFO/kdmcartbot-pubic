from telegram.ext import ContextTypes
from config import ADMINS
import logging

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMINS


async def send_to_all_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Отправляет сообщение всем администраторам"""
    success_count = 0
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message)
            success_count += 1
            logger.info(f"Сообщение отправлено администратору {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки администратору {admin_id}: {e}")

    return success_count > 0