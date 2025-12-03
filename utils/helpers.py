from aiogram import Bot
from aiogram.types import Message
import logging

logger = logging.getLogger(__name__)


async def check_admin_rights(bot: Bot, channel_id: int, user_id: int) -> bool:
    """Проверка прав администратора"""
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception as e:
        logger.error(f"Error checking admin rights: {e}")
        return False


async def check_bot_rights(bot: Bot, channel_id: int) -> tuple[bool, str]:
    """Проверка прав бота в канале"""
    try:
        member = await bot.get_chat_member(channel_id, bot.id)
        
        if member.status not in ['administrator', 'creator']:
            return False, "Бот не является администратором канала"
        
        if not getattr(member, 'can_post_messages', False):
            return False, "У бота нет прав на публикацию сообщений"
        
        return True, "OK"
    
    except Exception as e:
        logger.error(f"Error checking bot rights: {e}")
        return False, str(e)


def format_number(num: int) -> str:
    """Форматирование числа с разделителями"""
    return f"{num:,}".replace(",", " ")


def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезка текста с многоточием"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
