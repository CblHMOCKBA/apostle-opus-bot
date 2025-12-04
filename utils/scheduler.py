import asyncio
import logging
from datetime import datetime
import pytz

from aiogram import Bot

import database as db
from keyboards import parse_url_buttons

logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_now():
    """Текущее московское время"""
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)


def parse_db_time(time_str) -> datetime:
    """Парсинг времени из БД"""
    if isinstance(time_str, datetime):
        return time_str
    
    for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return datetime.now()


async def check_scheduled_posts(bot: Bot):
    """Проверка и публикация постов"""
    while True:
        try:
            posts = await db.get_pending_posts()
            now = get_moscow_now()  # Московское время!
            
            for post in posts:
                scheduled_time = parse_db_time(post['scheduled_time'])
                
                if scheduled_time <= now:
                    logger.info(f"Publishing post {post['id']} (scheduled: {scheduled_time}, now: {now})")
                    await publish_scheduled_post(bot, post)
        
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        
        await asyncio.sleep(30)  # Проверяем каждые 30 сек


async def publish_scheduled_post(bot: Bot, post):
    """Публикация поста"""
    try:
        settings = await db.get_user_settings(post['user_id'])
        parse_mode = settings['formatting'] if settings else 'HTML'
        disable_notification = not settings['notifications'] if settings else True
        
        keyboard = None
        if post['buttons']:
            keyboard = parse_url_buttons(post['buttons'])
        
        if post['media_type'] == 'photo' and post['media_file_id']:
            msg = await bot.send_photo(
                chat_id=post['channel_id'],
                photo=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif post['media_type'] == 'video' and post['media_file_id']:
            msg = await bot.send_video(
                chat_id=post['channel_id'],
                video=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif post['media_type'] == 'document' and post['media_file_id']:
            msg = await bot.send_document(
                chat_id=post['channel_id'],
                document=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        else:
            msg = await bot.send_message(
                chat_id=post['channel_id'],
                text=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        
        await db.update_scheduled_post_status(post['id'], 'published')
        await db.add_post_stats(post['channel_id'], msg.message_id)
        
        logger.info(f"Published post {post['id']}")
        
        try:
            await bot.send_message(
                chat_id=post['user_id'],
                text="✅ Отложенный пост опубликован!"
            )
        except:
            pass
        
        if post['delete_after']:
            asyncio.create_task(delete_post_later(bot, post['channel_id'], msg.message_id, post['delete_after']))
    
    except Exception as e:
        logger.error(f"Publish error: {e}")
        try:
            await bot.send_message(chat_id=post['user_id'], text=f"❌ Ошибка публикации:\n{e}")
        except:
            pass


async def delete_post_later(bot: Bot, channel_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Delete error: {e}")


def start_scheduler(bot: Bot):
    asyncio.create_task(check_scheduled_posts(bot))
    logger.info("Scheduler started (Moscow time)")
