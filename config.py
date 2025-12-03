import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8214171666:AAHrefgese3K053ukyWwOJ2kfleUcpuQ2-s")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Database
DATABASE_PATH = "bot_database.db"

# Default settings
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_FORMATTING = "HTML"
