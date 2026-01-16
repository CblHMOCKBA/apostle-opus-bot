#!/usr/bin/env python3
"""
Скрипт миграции базы данных - добавление поддержки альбомов
Запустить: python migrate_db.py
"""

import sqlite3
import sys

def migrate_database(db_path='bot_database.db'):
    """Миграция базы данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"🔄 Миграция базы данных: {db_path}")
        
        # Проверяем, есть ли уже поле album в scheduled_posts
        cursor.execute("PRAGMA table_info(scheduled_posts)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'album' not in columns:
            print("➕ Добавляем поле 'album' в таблицу scheduled_posts...")
            cursor.execute("ALTER TABLE scheduled_posts ADD COLUMN album TEXT")
            print("✅ Поле добавлено в scheduled_posts")
        else:
            print("ℹ️  Поле 'album' уже существует в scheduled_posts")
        
        # Проверяем таблицу templates
        cursor.execute("PRAGMA table_info(templates)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'album' not in columns:
            print("➕ Добавляем поле 'album' в таблицу templates...")
            cursor.execute("ALTER TABLE templates ADD COLUMN album TEXT")
            print("✅ Поле добавлено в templates")
        else:
            print("ℹ️  Поле 'album' уже существует в templates")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)
