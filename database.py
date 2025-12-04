import aiosqlite
import asyncio
from datetime import datetime
from config import DATABASE_PATH

# Блокировка для безопасной работы с БД
_db_lock = asyncio.Lock()


async def get_db():
    """Получить соединение с БД с настройками для конкурентности"""
    db = await aiosqlite.connect(DATABASE_PATH, timeout=30.0)
    await db.execute("PRAGMA journal_mode=WAL")  # Улучшает конкурентность
    await db.execute("PRAGMA busy_timeout=30000")  # 30 секунд ожидания при блокировке
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Инициализация базы данных"""
    async with _db_lock:
        db = await get_db()
        try:
            # Проверяем структуру таблицы channels
            cursor = await db.execute("PRAGMA table_info(channels)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            # Если таблица старая (с added_by), нужна миграция
            if 'added_by' in columns:
                # Создаём новую таблицу связей
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, channel_id)
                    )
                """)
                
                # Переносим связи из старой таблицы
                await db.execute("""
                    INSERT OR IGNORE INTO user_channels (user_id, channel_id)
                    SELECT added_by, channel_id FROM channels WHERE added_by IS NOT NULL
                """)
                await db.commit()
            else:
                # Создаём таблицу связей если её нет
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, channel_id)
                    )
                """)
            
            # Таблица каналов (если её нет)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER UNIQUE NOT NULL,
                    channel_username TEXT,
                    channel_title TEXT,
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
        finally:
            await db.close()


# ============ CHANNELS ============

async def add_channel(channel_id: int, username: str, title: str, added_by: int):
    """Добавить канал в БД и связать с пользователем"""
    async with _db_lock:
        db = await get_db()
        try:
            # Проверяем структуру БД
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_channels'"
            )
            has_new_structure = await cursor.fetchone() is not None
            
            if has_new_structure:
                # Новая структура
                await db.execute(
                    """INSERT INTO channels (channel_id, channel_username, channel_title) 
                       VALUES (?, ?, ?)
                       ON CONFLICT(channel_id) DO UPDATE SET 
                       channel_username = excluded.channel_username,
                       channel_title = excluded.channel_title""",
                    (channel_id, username, title)
                )
                await db.execute(
                    """INSERT OR IGNORE INTO user_channels (user_id, channel_id) 
                       VALUES (?, ?)""",
                    (added_by, channel_id)
                )
            else:
                # Старая структура
                await db.execute(
                    """INSERT OR REPLACE INTO channels 
                       (channel_id, channel_username, channel_title, added_by) 
                       VALUES (?, ?, ?, ?)""",
                    (channel_id, username, title, added_by)
                )
            await db.commit()
        finally:
            await db.close()


async def get_channels(user_id: int = None):
    """Получить список каналов пользователя"""
    db = await get_db()
    try:
        # Проверяем есть ли новая таблица user_channels
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_channels'"
        )
        has_new_structure = await cursor.fetchone() is not None
        
        if user_id:
            if has_new_structure:
                # Новая структура: связь через user_channels
                cursor = await db.execute(
                    """SELECT c.* FROM channels c
                       INNER JOIN user_channels uc ON c.channel_id = uc.channel_id
                       WHERE uc.user_id = ?""",
                    (user_id,)
                )
            else:
                # Старая структура: added_by в таблице channels
                cursor = await db.execute(
                    "SELECT * FROM channels WHERE added_by = ?", (user_id,)
                )
        else:
            cursor = await db.execute("SELECT * FROM channels")
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_channel_by_id(channel_id: int):
    """Получить канал по ID"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        )
        return await cursor.fetchone()
    finally:
        await db.close()


async def remove_channel(channel_id: int, user_id: int = None):
    """Удалить связь пользователя с каналом"""
    async with _db_lock:
        db = await get_db()
        try:
            # Проверяем структуру БД
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_channels'"
            )
            has_new_structure = await cursor.fetchone() is not None
            
            if has_new_structure and user_id:
                # Новая структура: удаляем только связь
                await db.execute(
                    "DELETE FROM user_channels WHERE channel_id = ? AND user_id = ?",
                    (channel_id, user_id)
                )
            else:
                # Старая структура или полное удаление
                await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
                if has_new_structure:
                    await db.execute("DELETE FROM user_channels WHERE channel_id = ?", (channel_id,))
            await db.commit()
        finally:
            await db.close()


# ============ USER SETTINGS ============

async def get_user_settings(user_id: int):
    """Получить настройки пользователя"""
    async with _db_lock:
        db = await get_db()
        try:
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
        finally:
            await db.close()


async def update_user_setting(user_id: int, setting: str, value):
    """Обновить настройку пользователя"""
    # Защита от SQL-инъекций - разрешаем только известные поля
    allowed_settings = {'formatting', 'notifications', 'link_preview', 'default_reactions', 'timezone'}
    if setting not in allowed_settings:
        raise ValueError(f"Invalid setting: {setting}")
    
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute(
                f"UPDATE users_settings SET {setting} = ? WHERE user_id = ?",
                (value, user_id)
            )
            await db.commit()
        finally:
            await db.close()


# ============ SCHEDULED POSTS ============

async def add_scheduled_post(channel_id: int, user_id: int, text: str, 
                             media_type: str, media_file_id: str, buttons: str,
                             scheduled_time: datetime, delete_after: int = None):
    """Добавить отложенный пост"""
    async with _db_lock:
        db = await get_db()
        try:
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
        finally:
            await db.close()


async def get_pending_posts():
    """Получить посты, готовые к публикации"""
    db = await get_db()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(
            """SELECT * FROM scheduled_posts 
               WHERE status = 'pending' AND scheduled_time <= ?""",
            (now,)
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_user_scheduled_posts(user_id: int):
    """Получить отложенные посты пользователя"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT sp.*, c.channel_username, c.channel_title 
               FROM scheduled_posts sp
               LEFT JOIN channels c ON sp.channel_id = c.channel_id
               WHERE sp.user_id = ? AND sp.status = 'pending'
               ORDER BY sp.scheduled_time ASC""",
            (user_id,)
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_scheduled_post(post_id: int):
    """Получить отложенный пост по ID"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)
        )
        return await cursor.fetchone()
    finally:
        await db.close()


async def update_scheduled_post_status(post_id: int, status: str):
    """Обновить статус отложенного поста"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute(
                "UPDATE scheduled_posts SET status = ? WHERE id = ?",
                (status, post_id)
            )
            await db.commit()
        finally:
            await db.close()


async def update_scheduled_post_time(post_id: int, new_time: datetime):
    """Изменить время отложенного поста"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute(
                "UPDATE scheduled_posts SET scheduled_time = ? WHERE id = ?",
                (new_time, post_id)
            )
            await db.commit()
        finally:
            await db.close()


async def update_scheduled_post_text(post_id: int, text: str):
    """Обновить текст отложенного поста"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute(
                "UPDATE scheduled_posts SET text = ? WHERE id = ?",
                (text, post_id)
            )
            await db.commit()
        finally:
            await db.close()


async def update_scheduled_post_buttons(post_id: int, buttons: str):
    """Обновить кнопки отложенного поста"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute(
                "UPDATE scheduled_posts SET buttons = ? WHERE id = ?",
                (buttons, post_id)
            )
            await db.commit()
        finally:
            await db.close()


async def delete_scheduled_post(post_id: int):
    """Удалить отложенный пост"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
            await db.commit()
        finally:
            await db.close()


# ============ STATS ============

async def add_post_stats(channel_id: int, message_id: int):
    """Добавить запись о посте для статистики"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO posts_stats (channel_id, message_id, posted_at)
                   VALUES (?, ?, ?)""",
                (channel_id, message_id, datetime.now())
            )
            await db.commit()
        finally:
            await db.close()


# ============ TEMPLATES ============

async def add_template(user_id: int, name: str, text: str, media_type: str,
                       media_file_id: str, buttons: str):
    """Добавить шаблон"""
    async with _db_lock:
        db = await get_db()
        try:
            cursor = await db.execute(
                """INSERT INTO templates 
                   (user_id, name, text, media_type, media_file_id, buttons)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, name, text, media_type, media_file_id, buttons)
            )
            await db.commit()
            return cursor.lastrowid
        finally:
            await db.close()


async def get_user_templates(user_id: int):
    """Получить шаблоны пользователя"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM templates WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_template(template_id: int):
    """Получить шаблон по ID"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        )
        return await cursor.fetchone()
    finally:
        await db.close()


async def delete_template(template_id: int):
    """Удалить шаблон"""
    async with _db_lock:
        db = await get_db()
        try:
            await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            await db.commit()
        finally:
            await db.close()
