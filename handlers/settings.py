from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import get_main_menu, get_settings_keyboard, get_channels_keyboard
import database as db

router = Router()


@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
async def show_settings(message: Message, state: FSMContext):
    """Показать настройки"""
    await state.clear()
    
    settings = await db.get_user_settings(message.from_user.id)
    
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите параметр для изменения:",
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(dict(settings))
    )


@router.callback_query(F.data == "toggle_formatting")
async def toggle_formatting(callback: CallbackQuery):
    """Переключение форматирования"""
    settings = await db.get_user_settings(callback.from_user.id)
    current = settings['formatting']
    
    new_value = 'Markdown' if current == 'HTML' else 'HTML'
    await db.update_user_setting(callback.from_user.id, 'formatting', new_value)
    
    settings = await db.get_user_settings(callback.from_user.id)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(dict(settings))
    )
    await callback.answer(f"Форматирование: {new_value}")


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    """Переключение уведомлений"""
    settings = await db.get_user_settings(callback.from_user.id)
    current = settings['notifications']
    
    new_value = 0 if current else 1
    await db.update_user_setting(callback.from_user.id, 'notifications', new_value)
    
    settings = await db.get_user_settings(callback.from_user.id)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(dict(settings))
    )
    
    status = "включены" if new_value else "отключены"
    await callback.answer(f"Звуковые уведомления {status}")


@router.callback_query(F.data == "toggle_link_preview")
async def toggle_link_preview(callback: CallbackQuery):
    """Переключение preview ссылок"""
    settings = await db.get_user_settings(callback.from_user.id)
    current = settings['link_preview']
    
    new_value = 0 if current else 1
    await db.update_user_setting(callback.from_user.id, 'link_preview', new_value)
    
    settings = await db.get_user_settings(callback.from_user.id)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(dict(settings))
    )
    
    status = "включен" if new_value else "отключен"
    await callback.answer(f"Preview ссылок {status}")


@router.callback_query(F.data == "set_timezone")
async def set_timezone(callback: CallbackQuery):
    """Настройка часового пояса"""
    timezones = [
        ("🕐 UTC", "UTC"),
        ("🇷🇺 Москва", "Europe/Moscow"),
        ("🇷🇺 Калининград", "Europe/Kaliningrad"),
        ("🇷🇺 Екатеринбург", "Asia/Yekaterinburg"),
        ("🇷🇺 Новосибирск", "Asia/Novosibirsk"),
        ("🇷🇺 Владивосток", "Asia/Vladivostok"),
        ("🇺🇦 Киев", "Europe/Kiev"),
        ("🇧🇾 Минск", "Europe/Minsk"),
        ("🇰🇿 Алматы", "Asia/Almaty"),
    ]
    
    buttons = []
    for name, tz in timezones:
        buttons.append([
            InlineKeyboardButton(text=name, callback_data=f"tz_{tz}")
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    ])
    
    await callback.message.edit_text(
        "🌍 <b>Выберите часовой пояс:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz_"))
async def timezone_selected(callback: CallbackQuery):
    """Часовой пояс выбран"""
    timezone = callback.data.replace("tz_", "")
    await db.update_user_setting(callback.from_user.id, 'timezone', timezone)
    
    settings = await db.get_user_settings(callback.from_user.id)
    
    await callback.message.edit_text(
        f"✅ <b>Часовой пояс установлен:</b> {timezone}\n\n"
        "⚙️ <b>Настройки</b>",
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(dict(settings))
    )
    await callback.answer(f"Часовой пояс: {timezone}")


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery):
    """Возврат в настройки"""
    settings = await db.get_user_settings(callback.from_user.id)
    
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите параметр для изменения:",
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(dict(settings))
    )
    await callback.answer()


@router.callback_query(F.data == "manage_channels")
async def manage_channels(callback: CallbackQuery):
    """Управление каналами"""
    channels = await db.get_channels(callback.from_user.id)
    
    if not channels:
        await callback.message.edit_text(
            "📢 <b>У вас нет подключенных каналов</b>\n\n"
            "Добавьте канал через меню создания поста.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
            ])
        )
        await callback.answer()
        return
    
    buttons = []
    for channel in channels:
        title = channel['channel_title'] or channel['channel_username'] or str(channel['channel_id'])
        buttons.append([
            InlineKeyboardButton(text=f"📢 {title}", callback_data=f"view_channel_{channel['channel_id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"remove_channel_{channel['channel_id']}")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    ])
    
    await callback.message.edit_text(
        f"📢 <b>Ваши каналы ({len(channels)})</b>\n\n"
        "Нажмите 🗑 для удаления канала:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_channel_"))
async def remove_channel_confirm(callback: CallbackQuery):
    """Подтверждение удаления канала"""
    channel_id = int(callback.data.split("_")[-1])
    channel = await db.get_channel_by_id(channel_id)
    
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return
    
    title = channel['channel_title'] or channel['channel_username'] or str(channel_id)
    
    await callback.message.edit_text(
        f"❓ <b>Удалить канал?</b>\n\n"
        f"📢 {title}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_remove_{channel_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="manage_channels")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_remove_"))
async def confirm_remove_channel(callback: CallbackQuery):
    """Удаление канала"""
    channel_id = int(callback.data.split("_")[-1])
    await db.remove_channel(channel_id)
    
    await callback.answer("Канал удален!")
    
    # Обновляем список
    channels = await db.get_channels(callback.from_user.id)
    
    if not channels:
        await callback.message.edit_text(
            "📢 <b>У вас нет подключенных каналов</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
            ])
        )
        return
    
    buttons = []
    for channel in channels:
        title = channel['channel_title'] or channel['channel_username'] or str(channel['channel_id'])
        buttons.append([
            InlineKeyboardButton(text=f"📢 {title}", callback_data=f"view_channel_{channel['channel_id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"remove_channel_{channel['channel_id']}")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    ])
    
    await callback.message.edit_text(
        f"📢 <b>Ваши каналы ({len(channels)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(Command("mychannels"))
async def my_channels_cmd(message: Message):
    """Список каналов через команду"""
    channels = await db.get_channels(message.from_user.id)
    
    if not channels:
        await message.answer(
            "📢 <b>У вас нет подключенных каналов</b>\n\n"
            "Добавьте канал через меню создания поста.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
    
    text = f"📢 <b>Ваши каналы ({len(channels)})</b>\n\n"
    for i, channel in enumerate(channels, 1):
        title = channel['channel_title'] or channel['channel_username'] or str(channel['channel_id'])
        username = f"@{channel['channel_username']}" if channel['channel_username'] else f"ID: {channel['channel_id']}"
        text += f"{i}. {title}\n   {username}\n\n"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu())
