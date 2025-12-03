from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from keyboards import (
    get_main_menu, get_scheduled_post_keyboard,
    get_back_inline_keyboard, parse_url_buttons
)
import database as db

router = Router()


class ScheduledStates(StatesGroup):
    """Состояния для работы с отложенными постами"""
    reschedule = State()


@router.message(F.text == "📅 Отложенные")
@router.message(Command("scheduled"))
async def show_scheduled_posts(message: Message, state: FSMContext):
    """Показать отложенные посты"""
    await state.clear()
    
    posts = await db.get_user_scheduled_posts(message.from_user.id)
    
    if not posts:
        await message.answer(
            "📅 <b>Отложенные посты</b>\n\n"
            "У вас нет отложенных постов.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        f"📅 <b>Отложенные посты ({len(posts)})</b>",
        parse_mode="HTML"
    )
    
    for post in posts:
        scheduled_time = datetime.strptime(post['scheduled_time'], "%Y-%m-%d %H:%M:%S")
        time_str = scheduled_time.strftime("%d.%m.%Y в %H:%M")
        
        channel_name = post['channel_title'] or post['channel_username'] or f"ID: {post['channel_id']}"
        text_preview = (post['text'][:50] + "...") if post['text'] and len(post['text']) > 50 else (post['text'] or "[Без текста]")
        
        media_icon = ""
        if post['media_type'] == 'photo':
            media_icon = "📷 "
        elif post['media_type'] == 'video':
            media_icon = "🎥 "
        elif post['media_type'] == 'document':
            media_icon = "📄 "
        
        await message.answer(
            f"📅 <b>Отложенный пост #{post['id']}</b>\n\n"
            f"{media_icon}📝 <i>{text_preview}</i>\n"
            f"⏰ Время: {time_str}\n"
            f"📢 Канал: {channel_name}",
            parse_mode="HTML",
            reply_markup=get_scheduled_post_keyboard(post['id'])
        )


@router.callback_query(F.data.startswith("publish_scheduled_"))
async def publish_scheduled_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Опубликовать отложенный пост сейчас"""
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("⚠️ Пост не найден", show_alert=True)
        return
    
    # Публикуем пост
    try:
        keyboard = None
        if post['buttons']:
            keyboard = parse_url_buttons(post['buttons'])
        
        settings = await db.get_user_settings(callback.from_user.id)
        parse_mode = settings['formatting'] if settings else 'HTML'
        disable_notification = not settings['notifications'] if settings else True
        
        if post['media_type'] == 'photo' and post['media_file_id']:
            await bot.send_photo(
                chat_id=post['channel_id'],
                photo=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif post['media_type'] == 'video' and post['media_file_id']:
            await bot.send_video(
                chat_id=post['channel_id'],
                video=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif post['media_type'] == 'document' and post['media_file_id']:
            await bot.send_document(
                chat_id=post['channel_id'],
                document=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        else:
            await bot.send_message(
                chat_id=post['channel_id'],
                text=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        
        await db.update_scheduled_post_status(post_id, 'published')
        
        await callback.message.edit_text(
            f"✅ <b>Пост #{post_id} опубликован!</b>",
            parse_mode="HTML"
        )
        await callback.answer("Пост опубликован!")
    
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("delete_scheduled_"))
async def delete_scheduled(callback: CallbackQuery, state: FSMContext):
    """Удалить отложенный пост"""
    post_id = int(callback.data.split("_")[-1])
    
    await db.delete_scheduled_post(post_id)
    
    await callback.message.edit_text(
        f"🗑 <b>Пост #{post_id} удален</b>",
        parse_mode="HTML"
    )
    await callback.answer("Пост удален")


@router.callback_query(F.data.startswith("reschedule_"))
async def reschedule_post(callback: CallbackQuery, state: FSMContext):
    """Изменить время отложенного поста"""
    post_id = int(callback.data.split("_")[-1])
    
    await state.update_data(reschedule_post_id=post_id)
    
    await callback.message.edit_text(
        "📅 <b>Введите новое время публикации:</b>\n\n"
        "Формат: <code>ЧЧ ММ ДД ММ</code>\n"
        "Пример: <code>14 00 04 12</code> — 4 декабря в 14:00",
        parse_mode="HTML",
        reply_markup=get_back_inline_keyboard("back_to_scheduled")
    )
    await state.set_state(ScheduledStates.reschedule)
    await callback.answer()


@router.message(ScheduledStates.reschedule, F.text)
async def reschedule_time_received(message: Message, state: FSMContext):
    """Получено новое время для отложенного поста"""
    try:
        parts = message.text.strip().split()
        if len(parts) != 4:
            raise ValueError("Неверный формат")
        
        hour, minute, day, month = map(int, parts)
        year = datetime.now().year
        
        if month < datetime.now().month:
            year += 1
        
        new_time = datetime(year, month, day, hour, minute)
        
        if new_time <= datetime.now():
            await message.answer(
                "⚠️ <b>Время должно быть в будущем</b>",
                parse_mode="HTML"
            )
            return
        
        data = await state.get_data()
        post_id = data.get('reschedule_post_id')
        
        await db.update_scheduled_post_time(post_id, new_time)
        await state.clear()
        
        time_str = new_time.strftime("%d %B в %H:%M")
        await message.answer(
            f"✅ <b>Время изменено!</b>\n\n"
            f"📅 Новое время публикации: {time_str}",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    
    except ValueError:
        await message.answer(
            "⚠️ <b>Неверный формат!</b>\n\n"
            "Используйте: <code>ЧЧ ММ ДД ММ</code>",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "back_to_scheduled")
async def back_to_scheduled(callback: CallbackQuery, state: FSMContext):
    """Вернуться к списку отложенных постов"""
    await state.clear()
    await callback.message.delete()
    
    # Создаем фейковое сообщение для вызова show_scheduled_posts
    await show_scheduled_posts(callback.message, state)
    await callback.answer()
