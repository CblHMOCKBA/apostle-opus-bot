import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота (ОБЯЗАТЕЛЬНО должен быть в переменных окружения)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавьте его в переменные окружения Railway.")

# Админы
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Database
DATABASE_PATH = "bot_database.db"

# Default settings
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_FORMATTING = "HTML"
