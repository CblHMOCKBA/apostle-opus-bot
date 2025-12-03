from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional


def get_channels_keyboard(channels: list, action: str = "select"):
    """Клавиатура выбора канала"""
    buttons = []
    for channel in channels:
        title = channel['channel_title'] or channel['channel_username'] or str(channel['channel_id'])
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 {title}",
                callback_data=f"channel_{action}_{channel['channel_id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel")
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_post_constructor_keyboard(has_text: bool = False, has_media: bool = False, 
                                   has_buttons: bool = False):
    """Клавиатура конструктора поста"""
    buttons = []
    
    # Основные элементы поста
    if has_text:
        buttons.append([
            InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")
        ])
    
    if has_media:
        buttons.append([
            InlineKeyboardButton(text="🖼 Изменить медиа", callback_data="edit_media"),
            InlineKeyboardButton(text="🗑 Удалить медиа", callback_data="remove_media")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🖼 Прикрепить медиафайл", callback_data="add_media")
        ])
    
    if has_buttons:
        buttons.append([
            InlineKeyboardButton(text="🔗 Изменить кнопки", callback_data="edit_buttons"),
            InlineKeyboardButton(text="🗑 Удалить кнопки", callback_data="remove_buttons")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🔗 Добавить URL-кнопки", callback_data="add_buttons")
        ])
    
    # Действия
    buttons.append([
        InlineKeyboardButton(text="👁 Предпросмотр", callback_data="preview")
    ])
    buttons.append([
        InlineKeyboardButton(text="📤 Далее", callback_data="next_step")
    ])
    buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_publish_keyboard():
    """Клавиатура публикации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Опубликовать", callback_data="publish_now")
        ],
        [
            InlineKeyboardButton(text="⏰ Отложить", callback_data="schedule_post")
        ],
        [
            InlineKeyboardButton(text="⏱ Таймер удаления", callback_data="set_delete_timer")
        ],
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data="back_to_edit")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")
        ]
    ])


def get_confirm_publish_keyboard():
    """Подтверждение публикации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, опубликовать", callback_data="confirm_publish")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_publish_menu")
        ]
    ])


def get_schedule_keyboard():
    """Клавиатура выбора времени отложенной публикации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏰ Через 1 час", callback_data="schedule_1h"),
            InlineKeyboardButton(text="⏰ Через 3 часа", callback_data="schedule_3h")
        ],
        [
            InlineKeyboardButton(text="⏰ Через 6 часов", callback_data="schedule_6h"),
            InlineKeyboardButton(text="🌅 Завтра в 9:00", callback_data="schedule_tomorrow")
        ],
        [
            InlineKeyboardButton(text="📅 Указать время", callback_data="schedule_custom")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_publish_menu")
        ]
    ])


def get_delete_timer_keyboard():
    """Клавиатура выбора таймера удаления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 час", callback_data="delete_1h"),
            InlineKeyboardButton(text="6 часов", callback_data="delete_6h")
        ],
        [
            InlineKeyboardButton(text="12 часов", callback_data="delete_12h"),
            InlineKeyboardButton(text="24 часа", callback_data="delete_24h")
        ],
        [
            InlineKeyboardButton(text="📅 Указать время", callback_data="delete_custom")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_publish_menu")
        ]
    ])


def get_view_post_keyboard(channel_username: str, message_id: int):
    """Кнопка для просмотра опубликованного поста"""
    if channel_username:
        url = f"https://t.me/{channel_username.lstrip('@')}/{message_id}"
    else:
        url = f"https://t.me/c/{message_id}"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 Посмотреть пост", url=url)
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")
        ]
    ])


def get_settings_keyboard(settings: dict):
    """Клавиатура настроек"""
    formatting = settings.get('formatting', 'HTML')
    notifications = "🔔 ВКЛ" if settings.get('notifications', 0) else "🔕 ВЫКЛ"
    link_preview = "✅ ВКЛ" if settings.get('link_preview', 1) else "❌ ВЫКЛ"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"📝 Форматирование: {formatting}", 
                callback_data="toggle_formatting"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔔 Уведомления: {notifications}", 
                callback_data="toggle_notifications"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔗 Preview ссылок: {link_preview}", 
                callback_data="toggle_link_preview"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌍 Часовой пояс", 
                callback_data="set_timezone"
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Управление каналами", 
                callback_data="manage_channels"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
        ]
    ])


def get_scheduled_post_keyboard(post_id: int):
    """Клавиатура для отложенного поста"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏰ Изменить время", callback_data=f"reschedule_{post_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_scheduled_{post_id}")
        ],
        [
            InlineKeyboardButton(text="📤 Опубликовать сейчас", callback_data=f"publish_scheduled_{post_id}")
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_scheduled_{post_id}")
        ]
    ])


def parse_url_buttons(text: str) -> Optional[InlineKeyboardMarkup]:
    """
    Парсинг URL-кнопок из текста
    Формат: Кнопка - http://url
    Разделитель | для горизонтального размещения
    """
    if not text or not text.strip():
        return None
    
    keyboard = []
    lines = text.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        row = []
        parts = line.split('|')
        
        for part in parts[:3]:  # Максимум 3 кнопки в ряд
            part = part.strip()
            if ' - ' in part:
                btn_parts = part.split(' - ', 1)
                if len(btn_parts) == 2:
                    btn_text = btn_parts[0].strip()
                    btn_url = btn_parts[1].strip()
                    if btn_text and btn_url:
                        # Проверяем URL
                        if btn_url.startswith(('http://', 'https://', 'tg://')):
                            row.append(InlineKeyboardButton(text=btn_text, url=btn_url))
        
        if row:
            keyboard.append(row)
    
    if keyboard:
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    return None


def get_back_inline_keyboard(callback_data: str = "back_to_main"):
    """Простая кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)]
    ])
