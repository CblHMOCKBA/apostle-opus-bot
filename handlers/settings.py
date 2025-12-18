from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import get_main_menu, get_cancel_keyboard
import database as db

router = Router()


class SettingsStates(StatesGroup):
    main = State()
    add_channel = State()


def get_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Управление каналами", callback_data="settings_channels")],
        [InlineKeyboardButton(text="📝 Форматирование", callback_data="settings_formatting")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications")],
        [InlineKeyboardButton(text="🔗 Превью ссылок", callback_data="settings_link_preview")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
    ])


@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
async def show_settings(message: Message, state: FSMContext):
    await state.clear()
    settings = await db.get_user_settings(message.from_user.id)
    
    formatting = settings['formatting'] if settings else 'HTML'
    notifications = "✅ Вкл" if settings and settings['notifications'] else "❌ Выкл"
    link_preview = "✅ Вкл" if settings and settings['link_preview'] else "❌ Выкл"
    
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"📝 Форматирование: <b>{formatting}</b>\n"
        f"🔔 Уведомления: <b>{notifications}</b>\n"
        f"🔗 Превью ссылок: <b>{link_preview}</b>"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_settings_keyboard())
    await state.set_state(SettingsStates.main)


@router.callback_query(F.data == "settings_back")
async def back_to_settings(callback: CallbackQuery, state: FSMContext):
    settings = await db.get_user_settings(callback.from_user.id)
    
    formatting = settings['formatting'] if settings else 'HTML'
    notifications = "✅ Вкл" if settings and settings['notifications'] else "❌ Выкл"
    link_preview = "✅ Вкл" if settings and settings['link_preview'] else "❌ Выкл"
    
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"📝 Форматирование: <b>{formatting}</b>\n"
        f"🔔 Уведомления: <b>{notifications}</b>\n"
        f"🔗 Превью ссылок: <b>{link_preview}</b>"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_settings_keyboard())
    await state.set_state(SettingsStates.main)
    await callback.answer()


# ============ УПРАВЛЕНИЕ КАНАЛАМИ ============

@router.callback_query(F.data == "settings_channels")
async def manage_channels(callback: CallbackQuery, state: FSMContext):
    channels = await db.get_channels(callback.from_user.id)
    
    if not channels:
        text = "📢 <b>Управление каналами</b>\n\nУ вас нет подключенных каналов."
        buttons = []
    else:
        text = f"📢 <b>Управление каналами ({len(channels)})</b>\n\n"
        buttons = []
        for ch in channels:
            name = ch['channel_title'] or ch['channel_username'] or str(ch['channel_id'])
            text += f"• {name}\n"
            buttons.append([
                InlineKeyboardButton(text=f"🗑 {name[:20]}", callback_data=f"remove_channel_{ch['channel_id']}")
            ])
    
    buttons.append([InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_new_channel")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data == "add_new_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📢 <b>Добавление канала</b>\n\n"
        "1. Добавьте бота в канал как администратора\n"
        "2. Дайте боту права на публикацию сообщений\n"
        "3. Перешлите мне любое сообщение из канала",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="settings_channels")]
        ])
    )
    await state.set_state(SettingsStates.add_channel)
    await callback.answer()


@router.message(SettingsStates.add_channel, F.forward_from_chat)
async def process_channel_forward(message: Message, state: FSMContext, bot: Bot):
    chat = message.forward_from_chat
    
    if chat.type != 'channel':
        await message.answer("⚠️ Это не канал. Перешлите сообщение из канала.")
        return
    
    try:
        # Проверяем права бота
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                "⚠️ Бот не является администратором канала.\n\n"
                "Добавьте бота как админа с правом публикации.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="add_new_channel")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_channels")]
                ])
            )
            return
        
        if not getattr(bot_member, 'can_post_messages', False):
            await message.answer(
                "⚠️ У бота нет прав на публикацию.\n\n"
                "Дайте боту право 'Публикация сообщений'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="add_new_channel")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_channels")]
                ])
            )
            return
        
        # Проверяем права пользователя
        user_member = await bot.get_chat_member(chat.id, message.from_user.id)
        if user_member.status not in ['creator', 'administrator']:
            await message.answer(
                "⚠️ Вы не являетесь администратором этого канала.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_channels")]
                ])
            )
            return
        
        # Добавляем канал
        await db.add_channel(
            channel_id=chat.id,
            username=chat.username,
            title=chat.title,
            added_by=message.from_user.id
        )
        
        await message.answer(
            f"✅ <b>Канал добавлен!</b>\n\n"
            f"📢 {chat.title or chat.username}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_new_channel")],
                [InlineKeyboardButton(text="📢 К каналам", callback_data="settings_channels")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
        await state.set_state(SettingsStates.main)
    
    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="add_new_channel")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_channels")]
            ])
        )


@router.message(SettingsStates.add_channel)
async def wrong_forward(message: Message):
    await message.answer(
        "⚠️ Перешлите сообщение из канала.\n\n"
        "Откройте канал, нажмите на любое сообщение и выберите 'Переслать'.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="settings_channels")]
        ])
    )


@router.callback_query(F.data.startswith("remove_channel_"))
async def remove_channel_confirm(callback: CallbackQuery):
    channel_id = int(callback.data.replace("remove_channel_", ""))
    channel = await db.get_channel_by_id(channel_id)
    
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return
    
    name = channel['channel_title'] or channel['channel_username'] or str(channel_id)
    
    await callback.message.edit_text(
        f"❓ <b>Удалить канал?</b>\n\n📢 {name}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_remove_{channel_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="settings_channels")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_remove_"))
async def remove_channel_do(callback: CallbackQuery):
    channel_id = int(callback.data.replace("confirm_remove_", ""))
    await db.remove_channel(channel_id)
    
    await callback.message.edit_text(
        "🗑 <b>Канал удалён</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 К каналам", callback_data="settings_channels")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer("Удалено!")


# ============ ФОРМАТИРОВАНИЕ ============

@router.callback_query(F.data == "settings_formatting")
async def formatting_settings(callback: CallbackQuery):
    settings = await db.get_user_settings(callback.from_user.id)
    current = settings['formatting'] if settings else 'HTML'
    
    await callback.message.edit_text(
        f"📝 <b>Форматирование</b>\n\n"
        f"Текущий режим: <b>{current}</b>\n\n"
        f"• <b>HTML</b> — &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;\n"
        f"• <b>Markdown</b> — *жирный*, _курсив_\n"
        f"• <b>Без форматирования</b> — текст как есть",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ HTML" if current == 'HTML' else "HTML",
                callback_data="set_format_HTML"
            )],
            [InlineKeyboardButton(
                text="✅ Markdown" if current == 'Markdown' else "Markdown",
                callback_data="set_format_Markdown"
            )],
            [InlineKeyboardButton(
                text="✅ Без форматирования" if current == 'None' else "Без форматирования",
                callback_data="set_format_None"
            )],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_format_"))
async def set_formatting(callback: CallbackQuery):
    format_type = callback.data.replace("set_format_", "")
    await db.update_user_setting(callback.from_user.id, 'formatting', format_type)
    await callback.answer(f"✅ Установлено: {format_type}")
    await formatting_settings(callback)


# ============ УВЕДОМЛЕНИЯ ============

@router.callback_query(F.data == "settings_notifications")
async def notifications_settings(callback: CallbackQuery):
    settings = await db.get_user_settings(callback.from_user.id)
    enabled = settings['notifications'] if settings else 0
    
    await callback.message.edit_text(
        f"🔔 <b>Уведомления при публикации</b>\n\n"
        f"Статус: <b>{'✅ Включены' if enabled else '❌ Выключены'}</b>\n\n"
        f"Если выключены — посты публикуются без звука.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔔 Включить" if not enabled else "🔕 Выключить",
                callback_data=f"toggle_notifications_{1 if not enabled else 0}"
            )],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_notifications_"))
async def toggle_notifications(callback: CallbackQuery):
    value = int(callback.data.replace("toggle_notifications_", ""))
    await db.update_user_setting(callback.from_user.id, 'notifications', value)
    await callback.answer("✅ Сохранено!")
    await notifications_settings(callback)


# ============ ПРЕВЬЮ ССЫЛОК ============

@router.callback_query(F.data == "settings_link_preview")
async def link_preview_settings(callback: CallbackQuery):
    settings = await db.get_user_settings(callback.from_user.id)
    enabled = settings['link_preview'] if settings else 1
    
    await callback.message.edit_text(
        f"🔗 <b>Превью ссылок</b>\n\n"
        f"Статус: <b>{'✅ Включено' if enabled else '❌ Выключено'}</b>\n\n"
        f"Показывать превью ссылок в постах.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 Включить" if not enabled else "❌ Выключить",
                callback_data=f"toggle_link_preview_{1 if not enabled else 0}"
            )],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_link_preview_"))
async def toggle_link_preview(callback: CallbackQuery):
    value = int(callback.data.replace("toggle_link_preview_", ""))
    await db.update_user_setting(callback.from_user.id, 'link_preview', value)
    await callback.answer("✅ Сохранено!")
    await link_preview_settings(callback)
