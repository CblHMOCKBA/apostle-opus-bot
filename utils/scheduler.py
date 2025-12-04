import asyncio
import logging
from datetime import datetime
import pytz

from aiogram import Bot

import database as db
from keyboards import parse_url_buttons

logger = logging.getLogger(__name__)

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_now():
    """Получить текущее время по Москве"""
    return datetime.now(MOSCOW_TZ)


def parse_scheduled_time(time_str):
    """Парсинг времени из БД с учётом разных форматов"""
    if isinstance(time_str, datetime):
        return time_str
    
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    return datetime.now()


async def check_scheduled_posts(bot: Bot):
    """Проверка и публикация отложенных постов"""
    while True:
        try:
            posts = await db.get_pending_posts()
            now = datetime.now()  # Используем naive datetime для сравнения с БД
            
            for post in posts:
                scheduled_time = parse_scheduled_time(post['scheduled_time'])
                
                if scheduled_time <= now:
                    logger.info(f"Publishing scheduled post {post['id']}")
                    await publish_scheduled_post(bot, post)
        
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        
        await asyncio.sleep(60)  # Проверяем каждую минуту


async def publish_scheduled_post(bot: Bot, post):
    """Публикация отложенного поста"""
    try:
        settings = await db.get_user_settings(post['user_id'])
        parse_mode = settings['formatting'] if settings else 'HTML'
        disable_notification = not settings['notifications'] if settings else True
        disable_web_page_preview = not settings['link_preview'] if settings else False
        
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
                disable_notification=disable_notification,
                disable_web_page_preview=disable_web_page_preview
            )
        
        # Обновляем статус и добавляем статистику
        await db.update_scheduled_post_status(post['id'], 'published')
        await db.add_post_stats(post['channel_id'], msg.message_id)
        
        logger.info(f"Published scheduled post {post['id']} to channel {post['channel_id']}")
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=post['user_id'],
                text=f"✅ Отложенный пост опубликован!",
                parse_mode="HTML"
            )
        except Exception:
            pass  # Пользователь мог заблокировать бота
        
        # Запускаем таймер удаления если установлен
        if post['delete_after']:
            asyncio.create_task(
                delete_post_later(bot, post['channel_id'], msg.message_id, post['delete_after'])
            )
    
    except Exception as e:
        logger.error(f"Error publishing scheduled post {post['id']}: {e}")
        
        # Уведомляем пользователя об ошибке
        try:
            await bot.send_message(
                chat_id=post['user_id'],
                text=f"❌ Ошибка публикации отложенного поста:\n{e}",
                parse_mode="HTML"
            )
        except Exception:
            pass


async def delete_post_later(bot: Bot, channel_id: int, message_id: int, delay: int):
    """Удаление поста через указанное время"""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=channel_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} from channel {channel_id}")
    except Exception as e:
        logger.error(f"Error deleting message: {e}")


def start_scheduler(bot: Bot):
    """Запуск планировщика"""
    asyncio.create_task(check_scheduled_posts(bot))
    logger.info("Scheduler started")
