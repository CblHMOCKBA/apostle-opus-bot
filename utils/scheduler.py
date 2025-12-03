import asyncio
import logging
from datetime import datetime
from aiogram import Bot

import database as db
from keyboards import parse_url_buttons

logger = logging.getLogger(__name__)


async def check_scheduled_posts(bot: Bot):
    """Проверка и публикация отложенных постов"""
    while True:
        try:
            posts = await db.get_pending_posts()
            
            for post in posts:
                try:
                    await publish_scheduled_post(bot, post)
                    await db.update_scheduled_post_status(post['id'], 'published')
                    logger.info(f"Published scheduled post {post['id']}")
                except Exception as e:
                    logger.error(f"Error publishing post {post['id']}: {e}")
                    await db.update_scheduled_post_status(post['id'], 'error')
        
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        
        # Проверяем каждую минуту
        await asyncio.sleep(60)


async def publish_scheduled_post(bot: Bot, post):
    """Публикация отложенного поста"""
    channel_id = post['channel_id']
    text = post['text']
    media_type = post['media_type']
    media_file_id = post['media_file_id']
    buttons_text = post['buttons']
    delete_after = post['delete_after']
    user_id = post['user_id']
    
    # Получаем настройки пользователя
    settings = await db.get_user_settings(user_id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    disable_notification = not settings['notifications'] if settings else True
    
    # Парсим кнопки
    keyboard = None
    if buttons_text:
        keyboard = parse_url_buttons(buttons_text)
    
    # Публикуем
    if media_type == 'photo' and media_file_id:
        msg = await bot.send_photo(
            chat_id=channel_id,
            photo=media_file_id,
            caption=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
    elif media_type == 'video' and media_file_id:
        msg = await bot.send_video(
            chat_id=channel_id,
            video=media_file_id,
            caption=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
    elif media_type == 'document' and media_file_id:
        msg = await bot.send_document(
            chat_id=channel_id,
            document=media_file_id,
            caption=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
    else:
        msg = await bot.send_message(
            chat_id=channel_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
    
    # Добавляем статистику
    await db.add_post_stats(channel_id, msg.message_id)
    
    # Если есть таймер удаления
    if delete_after:
        asyncio.create_task(delete_post_later(bot, channel_id, msg.message_id, delete_after))
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ <b>Отложенный пост опубликован!</b>\n\n"
                 f"📅 ID поста: #{post['id']}",
            parse_mode="HTML"
        )
    except Exception:
        pass  # Пользователь мог заблокировать бота


async def delete_post_later(bot: Bot, channel_id: int, message_id: int, delay: int):
    """Удаление поста через указанное время"""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} from {channel_id}")
    except Exception as e:
        logger.error(f"Error deleting message: {e}")


def start_scheduler(bot: Bot):
    """Запуск планировщика"""
    asyncio.create_task(check_scheduled_posts(bot))
    logger.info("Scheduler started")
