from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import pytz

from keyboards import get_main_menu, parse_url_buttons
import database as db

router = Router()

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_now():
    """Московское время без tzinfo для сравнения с БД"""
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)


def parse_db_time(time_str) -> datetime:
    """Парсинг времени из БД"""
    if isinstance(time_str, datetime):
        return time_str
    for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return datetime.now()


class ScheduledStates(StatesGroup):
    viewing = State()
    reschedule = State()
    edit_text = State()
    edit_buttons = State()


@router.message(F.text == "📅 Отложенные")
@router.message(Command("scheduled"))
async def show_scheduled_posts(message: Message, state: FSMContext):
    """Список отложенных постов"""
    await state.clear()
    
    posts = await db.get_user_scheduled_posts(message.from_user.id)
    
    if not posts:
        await message.answer(
            "📅 <b>Отложенные посты</b>\n\nУ вас нет запланированных публикаций.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
    
    now = get_moscow_now()
    text = f"📅 <b>Отложенные посты ({len(posts)})</b>\n"
    text += f"🕐 Сейчас: {now.strftime('%H:%M')} МСК\n\n"
    
    buttons = []
    for post in posts[:10]:
        scheduled = parse_db_time(post['scheduled_time'])
        time_str = scheduled.strftime("%d.%m %H:%M")
        preview = (post['text'] or '[Медиа]')[:25] + "..."
        
        text += f"📌 {time_str} — {preview}\n"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"📝 {time_str} — {preview[:15]}",
                callback_data=f"sched_view_{post['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")])
    
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(ScheduledStates.viewing)


@router.callback_query(F.data.startswith("sched_view_"))
async def view_scheduled_post(callback: CallbackQuery, state: FSMContext):
    """Просмотр поста"""
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    await state.update_data(current_post_id=post_id)
    
    scheduled = parse_db_time(post['scheduled_time'])
    now = get_moscow_now()
    
    text = f"📅 <b>Отложенный пост</b>\n\n"
    text += f"⏰ <b>Публикация:</b> {scheduled.strftime('%d.%m.%Y в %H:%M')} МСК\n"
    text += f"🕐 <b>Сейчас:</b> {now.strftime('%H:%M')} МСК\n"
    
    if post['text']:
        text += f"\n📝 <b>Текст:</b>\n<i>{post['text'][:200]}{'...' if len(post['text']) > 200 else ''}</i>\n"
    
    if post['media_type']:
        media_names = {'photo': '📷 Фото', 'video': '🎥 Видео', 'document': '📄 Документ'}
        text += f"\n📎 <b>Медиа:</b> {media_names.get(post['media_type'], post['media_type'])}\n"
    
    if post['buttons']:
        text += f"\n🔗 <b>Кнопки:</b> Да\n"
    
    if post['delete_after']:
        hours = post['delete_after'] // 3600
        mins = (post['delete_after'] % 3600) // 60
        text += f"\n⏱ <b>Удалить через:</b> {hours}ч {mins}м\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Опубликовать сейчас", callback_data=f"sched_publish_{post_id}")],
        [InlineKeyboardButton(text="⏰ Изменить время", callback_data=f"sched_time_{post_id}")],
        [
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"sched_edit_text_{post_id}"),
            InlineKeyboardButton(text="🔗 Кнопки", callback_data=f"sched_edit_btns_{post_id}")
        ],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"sched_delete_{post_id}")],
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="sched_back_list")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ============ РЕДАКТИРОВАНИЕ ТЕКСТА ============

@router.callback_query(F.data.startswith("sched_edit_text_"))
async def edit_text_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    await state.update_data(edit_post_id=post_id)
    
    await callback.message.edit_text(
        f"✏️ <b>Текущий текст:</b>\n\n"
        f"<i>{post['text'] or '[Пусто]'}</i>\n\n"
        f"Отправьте новый текст:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"sched_view_{post_id}")]
        ])
    )
    await state.set_state(ScheduledStates.edit_text)
    await callback.answer()


@router.message(ScheduledStates.edit_text, F.text)
async def save_text(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get('edit_post_id')
    
    if not post_id:
        await message.answer("Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    await db.update_scheduled_post_text(post_id, message.text)
    
    await message.answer(
        "✅ <b>Текст обновлён!</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]
        ])
    )
    await state.set_state(ScheduledStates.viewing)


# ============ РЕДАКТИРОВАНИЕ КНОПОК ============

@router.callback_query(F.data.startswith("sched_edit_btns_"))
async def edit_buttons_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    await state.update_data(edit_post_id=post_id)
    
    await callback.message.edit_text(
        f"🔗 <b>Текущие кнопки:</b>\n\n"
        f"<code>{post['buttons'] or '[Нет]'}</code>\n\n"
        f"Формат: <code>Текст - http://url</code>\n"
        f"Отправьте <code>удалить</code> чтобы убрать кнопки",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"sched_view_{post_id}")]
        ])
    )
    await state.set_state(ScheduledStates.edit_buttons)
    await callback.answer()


@router.message(ScheduledStates.edit_buttons, F.text)
async def save_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get('edit_post_id')
    
    if not post_id:
        await message.answer("Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if message.text.lower() == 'удалить':
        await db.update_scheduled_post_buttons(post_id, None)
        await message.answer("✅ Кнопки удалены!")
    else:
        keyboard = parse_url_buttons(message.text)
        if not keyboard:
            await message.answer("⚠️ Неверный формат!\nИспользуйте: <code>Текст - http://url</code>", parse_mode="HTML")
            return
        await db.update_scheduled_post_buttons(post_id, message.text)
        await message.answer("✅ Кнопки обновлены!")
    
    await message.answer(
        "Выберите:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]
        ])
    )
    await state.set_state(ScheduledStates.viewing)


# ============ ИЗМЕНЕНИЕ ВРЕМЕНИ ============

@router.callback_query(F.data.startswith("sched_time_"))
async def change_time_menu(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[-1])
    await state.update_data(reschedule_post_id=post_id)
    
    now = get_moscow_now()
    
    await callback.message.edit_text(
        f"⏰ <b>Изменить время</b>\n\n"
        f"🕐 Сейчас: <b>{now.strftime('%H:%M')}</b> МСК",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="+1 час", callback_data=f"resched_1h_{post_id}"),
                InlineKeyboardButton(text="+3 часа", callback_data=f"resched_3h_{post_id}")
            ],
            [
                InlineKeyboardButton(text="+6 часов", callback_data=f"resched_6h_{post_id}"),
                InlineKeyboardButton(text="Завтра 9:00", callback_data=f"resched_tomorrow_{post_id}")
            ],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"resched_custom_{post_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sched_view_{post_id}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("resched_"))
async def reschedule_action(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    action = parts[1]
    post_id = int(parts[2])
    
    now = get_moscow_now()
    
    if action == "1h":
        new_time = now + timedelta(hours=1)
    elif action == "3h":
        new_time = now + timedelta(hours=3)
    elif action == "6h":
        new_time = now + timedelta(hours=6)
    elif action == "tomorrow":
        tomorrow = now + timedelta(days=1)
        new_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    elif action == "custom":
        await callback.message.edit_text(
            f"📅 <b>Введите время (МСК):</b>\n\n"
            f"Формат: <code>ЧЧ ММ ДД ММ</code>\n"
            f"Пример: <code>14 30 05 12</code> = 5 декабря 14:30\n\n"
            f"🕐 Сейчас: {now.strftime('%H:%M')} МСК",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sched_time_{post_id}")]
            ])
        )
        await state.update_data(reschedule_post_id=post_id)
        await state.set_state(ScheduledStates.reschedule)
        await callback.answer()
        return
    else:
        await callback.answer("Ошибка")
        return
    
    # Сохраняем московское время напрямую
    await db.update_scheduled_post_time(post_id, new_time)
    
    await callback.message.edit_text(
        f"✅ <b>Время изменено!</b>\n\n"
        f"📅 Публикация: {new_time.strftime('%d.%m в %H:%M')} МСК",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer("Готово!")


@router.message(ScheduledStates.reschedule, F.text)
async def reschedule_custom(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get('reschedule_post_id')
    
    if not post_id:
        await message.answer("Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 4:
            raise ValueError()
        
        hour, minute, day, month = map(int, parts)
        now = get_moscow_now()
        year = now.year
        
        if month < now.month or (month == now.month and day < now.day):
            year += 1
        
        new_time = datetime(year, month, day, hour, minute)
        
        if new_time <= now:
            await message.answer("⚠️ Время должно быть в будущем!")
            return
        
        await db.update_scheduled_post_time(post_id, new_time)
        
        await message.answer(
            f"✅ <b>Время изменено!</b>\n\n"
            f"📅 Публикация: {new_time.strftime('%d.%m в %H:%M')} МСК",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
                [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]
            ])
        )
        await state.set_state(ScheduledStates.viewing)
    
    except ValueError:
        await message.answer("⚠️ Формат: <code>ЧЧ ММ ДД ММ</code>\nПример: <code>14 30 05 12</code>", parse_mode="HTML")


# ============ ПУБЛИКАЦИЯ СЕЙЧАС ============

@router.callback_query(F.data.startswith("sched_publish_"))
async def publish_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    settings = await db.get_user_settings(callback.from_user.id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    
    keyboard = parse_url_buttons(post['buttons']) if post['buttons'] else None
    
    try:
        if post['media_type'] == 'photo':
            msg = await bot.send_photo(post['channel_id'], post['media_file_id'], caption=post['text'], reply_markup=keyboard, parse_mode=parse_mode)
        elif post['media_type'] == 'video':
            msg = await bot.send_video(post['channel_id'], post['media_file_id'], caption=post['text'], reply_markup=keyboard, parse_mode=parse_mode)
        elif post['media_type'] == 'document':
            msg = await bot.send_document(post['channel_id'], post['media_file_id'], caption=post['text'], reply_markup=keyboard, parse_mode=parse_mode)
        else:
            msg = await bot.send_message(post['channel_id'], post['text'], reply_markup=keyboard, parse_mode=parse_mode)
        
        await db.update_scheduled_post_status(post_id, 'published')
        await db.add_post_stats(post['channel_id'], msg.message_id)
        
        channel = await db.get_channel_by_id(post['channel_id'])
        username = channel['channel_username'] if channel else None
        
        if username:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Посмотреть", url=f"https://t.me/{username.lstrip('@')}/{msg.message_id}")],
                [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]])
        
        await callback.message.edit_text("✅ <b>Опубликовано!</b>", parse_mode="HTML", reply_markup=kb)
    
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sched_view_{post_id}")]]))
    
    await callback.answer()


# ============ УДАЛЕНИЕ ============

@router.callback_query(F.data.startswith("sched_delete_"))
async def delete_confirm(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    
    await callback.message.edit_text(
        "❓ <b>Удалить пост?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"sched_do_delete_{post_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"sched_view_{post_id}")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_do_delete_"))
async def delete_post(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    await db.delete_scheduled_post(post_id)
    
    await callback.message.edit_text(
        "🗑 <b>Удалено</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К списку", callback_data="sched_back_list")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "sched_back_list")
async def back_to_list(callback: CallbackQuery, state: FSMContext):
    posts = await db.get_user_scheduled_posts(callback.from_user.id)
    
    if not posts:
        await callback.message.edit_text(
            "📅 <b>Отложенные посты</b>\n\nПусто",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")]])
        )
        return
    
    buttons = []
    for post in posts[:10]:
        scheduled = parse_db_time(post['scheduled_time'])
        time_str = scheduled.strftime("%d.%m %H:%M")
        preview = (post['text'] or '[Медиа]')[:15]
        buttons.append([InlineKeyboardButton(text=f"📝 {time_str} — {preview}", callback_data=f"sched_view_{post['id']}")])
    
    buttons.append([InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_main")])
    
    await callback.message.edit_text(f"📅 <b>Отложенные ({len(posts)})</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()
