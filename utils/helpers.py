from aiogram import Bot
from aiogram.types import ChatMember


async def check_admin_rights(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Проверить, является ли пользователь администратором канала"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False


async def check_bot_rights(bot: Bot, chat_id: int) -> dict:
    """Проверить права бота в канале"""
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        return {
            'is_admin': member.status in ['administrator', 'creator'],
            'can_post': getattr(member, 'can_post_messages', False) or member.status == 'creator'
        }
    except Exception:
        return {'is_admin': False, 'can_post': False}


def format_number(num: int) -> str:
    """Форматирование числа с разделителями"""
    return f"{num:,}".replace(",", " ")


def truncate_text(text: str, max_length: int = 50) -> str:
    """Обрезать текст с многоточием"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
