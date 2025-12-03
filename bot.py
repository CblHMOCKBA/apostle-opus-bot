import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
from utils import start_scheduler

from handlers import (
    start_router,
    create_post_router,
    scheduled_router,
    edit_post_router,
    settings_router,
    stats_router,
    templates_router,
    polls_router
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    
    # Инициализация базы данных
    await db.init_db()
    logger.info("Database initialized")
    
    # Создание бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создание диспетчера
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(create_post_router)
    dp.include_router(scheduled_router)
    dp.include_router(edit_post_router)
    dp.include_router(settings_router)
    dp.include_router(stats_router)
    dp.include_router(templates_router)
    dp.include_router(polls_router)
    
    # Запуск планировщика
    start_scheduler(bot)
    logger.info("Scheduler started")
    
    # Информация о боте
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")
    
    # Запуск polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
