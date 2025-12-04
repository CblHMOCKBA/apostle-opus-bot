import aiosqlite
import asyncio
from datetime import datetime
from config import DATABASE_PATH


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Таблица каналов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE NOT NULL,
                channel_username TEXT,
                channel_title TEXT,
                added_by INTEGER,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица настроек пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users_settings (
                user_id INTEGER PRIMARY KEY,
                formatting TEXT DEFAULT 'HTML',
                notifications INTEGER DEFAULT 0,
                link_preview INTEGER DEFAULT 1,
                default_reactions TEXT,
                timezone TEXT DEFAULT 'Europe/Moscow'
            )
        """)
        
        # Таблица отложенных постов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                buttons TEXT,
                scheduled_time DATETIME NOT NULL,
                delete_after INTEGER,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица статистики постов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS posts_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                message_id INTEGER,
                posted_at DATETIME,
                views INTEGER DEFAULT 0,
                reactions TEXT
            )
        """)
        
        # Таблица шаблонов постов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                buttons TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()


# ============ CHANNELS ============

async def add_channel(channel_id: int, username: str, title: str, added_by: int):
    """Добавить канал в БД"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO channels 
               (channel_id, channel_username, channel_title, added_by) 
               VALUES (?, ?, ?, ?)""",
            (channel_id, username, title, added_by)
        )
        await db.commit()


async def get_channels(user_id: int = None):
    """Получить список каналов"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if user_id:
            cursor = await db.execute(
                "SELECT * FROM channels WHERE added_by = ?", (user_id,)
            )
        else:
            cursor = await db.execute("SELECT * FROM channels")
        return await cursor.fetchall()


async def get_channel_by_id(channel_id: int):
    """Получить канал по ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        )
        return await cursor.fetchone()


async def remove_channel(channel_id: int):
    """Удалить канал"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()


# ============ USER SETTINGS ============

async def get_user_settings(user_id: int):
    """Получить настройки пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users_settings WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            # Создаем настройки по умолчанию
            await db.execute(
                "INSERT INTO users_settings (user_id) VALUES (?)", (user_id,)
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM users_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
        return row


async def update_user_setting(user_id: int, setting: str, value):
    """Обновить настройку пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE users_settings SET {setting} = ? WHERE user_id = ?",
            (value, user_id)
        )
        await db.commit()


# ============ SCHEDULED POSTS ============

async def add_scheduled_post(channel_id: int, user_id: int, text: str, 
                             media_type: str, media_file_id: str, buttons: str,
                             scheduled_time: datetime, delete_after: int = None):
    """Добавить отложенный пост"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO scheduled_posts 
               (channel_id, user_id, text, media_type, media_file_id, buttons, 
                scheduled_time, delete_after)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (channel_id, user_id, text, media_type, media_file_id, buttons,
             scheduled_time, delete_after)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_posts():
    """Получить посты, готовые к публикации"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(
            """SELECT * FROM scheduled_posts 
               WHERE status = 'pending' AND scheduled_time <= ?""",
            (now,)
        )
        return await cursor.fetchall()


async def get_user_scheduled_posts(user_id: int):
    """Получить отложенные посты пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT sp.*, c.channel_username, c.channel_title 
               FROM scheduled_posts sp
               LEFT JOIN channels c ON sp.channel_id = c.channel_id
               WHERE sp.user_id = ? AND sp.status = 'pending'
               ORDER BY sp.scheduled_time ASC""",
            (user_id,)
        )
        return await cursor.fetchall()


async def get_scheduled_post(post_id: int):
    """Получить отложенный пост по ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)
        )
        return await cursor.fetchone()


async def update_scheduled_post_status(post_id: int, status: str):
    """Обновить статус отложенного поста"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE scheduled_posts SET status = ? WHERE id = ?",
            (status, post_id)
        )
        await db.commit()


async def update_scheduled_post_time(post_id: int, new_time: datetime):
    """Изменить время отложенного поста"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE scheduled_posts SET scheduled_time = ? WHERE id = ?",
            (new_time, post_id)
        )
        await db.commit()


async def update_scheduled_post_text(post_id: int, text: str):
    """Обновить текст отложенного поста"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE scheduled_posts SET text = ? WHERE id = ?",
            (text, post_id)
        )
        await db.commit()


async def update_scheduled_post_buttons(post_id: int, buttons: str):
    """Обновить кнопки отложенного поста"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE scheduled_posts SET buttons = ? WHERE id = ?",
            (buttons, post_id)
        )
        await db.commit()


async def delete_scheduled_post(post_id: int):
    """Удалить отложенный пост"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
        await db.commit()


# ============ STATS ============

async def add_post_stats(channel_id: int, message_id: int):
    """Добавить запись о посте для статистики"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO posts_stats (channel_id, message_id, posted_at)
               VALUES (?, ?, ?)""",
            (channel_id, message_id, datetime.now())
        )
        await db.commit()


# ============ TEMPLATES ============

async def add_template(user_id: int, name: str, text: str, media_type: str,
                       media_file_id: str, buttons: str):
    """Добавить шаблон"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO templates 
               (user_id, name, text, media_type, media_file_id, buttons)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, name, text, media_type, media_file_id, buttons)
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_templates(user_id: int):
    """Получить шаблоны пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM templates WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return await cursor.fetchall()


async def get_template(template_id: int):
    """Получить шаблон по ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        )
        return await cursor.fetchone()


async def delete_template(template_id: int):
    """Удалить шаблон"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        await db.commit()
