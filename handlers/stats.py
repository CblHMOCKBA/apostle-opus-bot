from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import get_main_menu, get_channels_keyboard
import database as db

router = Router()


@router.message(F.text == "📊 Статистика")
@router.message(Command("stats"))
async def show_stats(message: Message, state: FSMContext, bot: Bot):
    """Показать статистику"""
    await state.clear()
    
    channels = await db.get_channels(message.from_user.id)
    
    if not channels:
        await message.answer(
            "📊 <b>Статистика</b>\n\n"
            "У вас нет подключенных каналов.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
    
    if len(channels) == 1:
        await show_channel_stats(message, channels[0]['channel_id'], bot)
    else:
        buttons = []
        for channel in channels:
            title = channel['channel_title'] or channel['channel_username'] or str(channel['channel_id'])
            buttons.append([
                InlineKeyboardButton(
                    text=f"📊 {title}",
                    callback_data=f"stats_{channel['channel_id']}"
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
        ])
        
        await message.answer(
            "📊 <b>Выберите канал для просмотра статистики:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


async def show_channel_stats(message: Message, channel_id: int, bot: Bot):
    """Показать статистику канала"""
    try:
        chat = await bot.get_chat(channel_id)
        member_count = await bot.get_chat_member_count(channel_id)
        
        channel = await db.get_channel_by_id(channel_id)
        title = channel['channel_title'] if channel else chat.title
        username = f"@{chat.username}" if chat.username else f"ID: {channel_id}"
        
        # Базовая статистика
        text = f"""📊 <b>Статистика канала</b>

📢 <b>{title}</b>
{username}

👥 <b>Подписчиков:</b> {member_count:,}

<i>📈 Расширенная статистика в разработке...</i>

<i>Для полной статистики используйте @TGStat_Bot или Telegram Analytics.</i>"""
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_stats_{channel_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
            ])
        )
    
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка получения статистики:</b>\n{e}",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )


@router.callback_query(F.data.startswith("stats_"))
async def stats_channel_selected(callback: CallbackQuery, bot: Bot):
    """Выбран канал для статистики"""
    channel_id = int(callback.data.split("_")[-1])
    
    try:
        chat = await bot.get_chat(channel_id)
        member_count = await bot.get_chat_member_count(channel_id)
        
        channel = await db.get_channel_by_id(channel_id)
        title = channel['channel_title'] if channel else chat.title
        username = f"@{chat.username}" if chat.username else f"ID: {channel_id}"
        
        text = f"""📊 <b>Статистика канала</b>

📢 <b>{title}</b>
{username}

👥 <b>Подписчиков:</b> {member_count:,}

<i>📈 Расширенная статистика в разработке...</i>"""
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_stats_{channel_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
            ])
        )
    
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("refresh_stats_"))
async def refresh_stats(callback: CallbackQuery, bot: Bot):
    """Обновление статистики"""
    channel_id = int(callback.data.split("_")[-1])
    
    try:
        chat = await bot.get_chat(channel_id)
        member_count = await bot.get_chat_member_count(channel_id)
        
        channel = await db.get_channel_by_id(channel_id)
        title = channel['channel_title'] if channel else chat.title
        username = f"@{chat.username}" if chat.username else f"ID: {channel_id}"
        
        text = f"""📊 <b>Статистика канала</b>

📢 <b>{title}</b>
{username}

👥 <b>Подписчиков:</b> {member_count:,}

<i>🔄 Обновлено</i>"""
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_stats_{channel_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
            ])
        )
        await callback.answer("Статистика обновлена!")
    
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
