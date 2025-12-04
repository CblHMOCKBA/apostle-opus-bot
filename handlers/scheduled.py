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

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_now():
    """Получить текущее время по Москве"""
    return datetime.now(MOSCOW_TZ)


def parse_scheduled_time(time_str):
    """Парсинг времени из БД с учётом разных форматов"""
    if isinstance(time_str, datetime):
        return time_str
    
    # Пробуем разные форматы
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",  # С микросекундами
        "%Y-%m-%d %H:%M:%S",     # Без микросекунд
        "%Y-%m-%d %H:%M",        # Только часы и минуты
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    # Если ничего не подошло, возвращаем текущее время
    return datetime.now()


class ScheduledStates(StatesGroup):
    """Состояния для работы с отложенными постами"""
    viewing = State()
    reschedule = State()
    edit_text = State()
    edit_buttons = State()


@router.message(F.text == "📅 Отложенные")
@router.message(Command("scheduled"))
async def show_scheduled_posts(message: Message, state: FSMContext):
    """Показать отложенные посты"""
    await state.clear()
    
    posts = await db.get_user_scheduled_posts(message.from_user.id)
    
    if not posts:
        await message.answer(
            "📅 <b>Отложенные посты</b>\n\n"
            "У вас нет запланированных публикаций.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
    
    now = get_moscow_now()
    
    text = f"📅 <b>Отложенные посты ({len(posts)})</b>\n\n"
    
    buttons = []
    for post in posts[:10]:  # Показываем только 10 последних
        scheduled_time = parse_scheduled_time(post['scheduled_time'])
        
        # Форматируем время
        time_str = scheduled_time.strftime("%d.%m в %H:%M")
        
        # Превью текста
        preview = (post['text'] or '[Медиа]')[:30]
        if len(post['text'] or '') > 30:
            preview += "..."
        
        channel_name = post['channel_title'] or post['channel_username'] or 'Канал'
        
        text += f"📌 {time_str} — {preview}\n"
        text += f"   └ 📢 {channel_name}\n\n"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"📝 {time_str} — {preview[:15]}...",
                callback_data=f"sched_view_{post['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(ScheduledStates.viewing)


@router.callback_query(F.data.startswith("sched_view_"))
async def view_scheduled_post(callback: CallbackQuery, state: FSMContext):
    """Просмотр отложенного поста"""
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    await state.update_data(current_post_id=post_id)
    
    scheduled_time = parse_scheduled_time(post['scheduled_time'])
    time_str = scheduled_time.strftime("%d.%m.%Y в %H:%M")
    
    text = f"📅 <b>Отложенный пост</b>\n\n"
    text += f"⏰ <b>Время:</b> {time_str}\n"
    
    if post['text']:
        text += f"\n📝 <b>Текст:</b>\n<i>{post['text'][:200]}{'...' if len(post['text']) > 200 else ''}</i>\n"
    
    if post['media_type']:
        text += f"\n📎 <b>Медиа:</b> {post['media_type']}\n"
    
    if post['buttons']:
        text += f"\n🔗 <b>Кнопки:</b> Да\n"
    
    if post['delete_after']:
        hours = post['delete_after'] // 3600
        text += f"\n⏱ <b>Удалить через:</b> {hours} ч.\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Опубликовать сейчас", callback_data=f"sched_publish_{post_id}")],
            [InlineKeyboardButton(text="⏰ Изменить время", callback_data=f"sched_time_{post_id}")],
            [
                InlineKeyboardButton(text="✏️ Текст", callback_data=f"sched_edit_text_{post_id}"),
                InlineKeyboardButton(text="🔗 Кнопки", callback_data=f"sched_edit_btns_{post_id}")
            ],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"sched_delete_{post_id}")],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data="sched_back_list")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_edit_text_"))
async def edit_scheduled_text(callback: CallbackQuery, state: FSMContext):
    """Редактирование текста отложенного поста"""
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    await state.update_data(edit_post_id=post_id)
    
    current_text = post['text'] or '[Пусто]'
    
    await callback.message.edit_text(
        f"✏️ <b>Текущий текст:</b>\n\n"
        f"<i>{current_text[:500]}</i>\n\n"
        f"Отправьте новый текст:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"sched_view_{post_id}")]
        ])
    )
    await state.set_state(ScheduledStates.edit_text)
    await callback.answer()


@router.message(ScheduledStates.edit_text, F.text)
async def save_scheduled_text(message: Message, state: FSMContext):
    """Сохранение нового текста"""
    data = await state.get_data()
    post_id = data.get('edit_post_id')
    
    if not post_id:
        await message.answer("Ошибка. Попробуйте снова.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    await db.update_scheduled_post_text(post_id, message.text)
    
    await message.answer(
        "✅ <b>Текст обновлён!</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ])
    )
    await state.set_state(ScheduledStates.viewing)


@router.callback_query(F.data.startswith("sched_edit_btns_"))
async def edit_scheduled_buttons(callback: CallbackQuery, state: FSMContext):
    """Редактирование кнопок отложенного поста"""
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    await state.update_data(edit_post_id=post_id)
    
    current_buttons = post['buttons'] or '[Нет кнопок]'
    
    await callback.message.edit_text(
        f"🔗 <b>Текущие кнопки:</b>\n\n"
        f"<code>{current_buttons}</code>\n\n"
        f"Отправьте новые кнопки в формате:\n"
        f"<code>Кнопка - http://url</code>\n\n"
        f"Или отправьте <code>удалить</code> чтобы убрать кнопки.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"sched_view_{post_id}")]
        ])
    )
    await state.set_state(ScheduledStates.edit_buttons)
    await callback.answer()


@router.message(ScheduledStates.edit_buttons, F.text)
async def save_scheduled_buttons(message: Message, state: FSMContext):
    """Сохранение новых кнопок"""
    data = await state.get_data()
    post_id = data.get('edit_post_id')
    
    if not post_id:
        await message.answer("Ошибка. Попробуйте снова.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if message.text.lower() == 'удалить':
        await db.update_scheduled_post_buttons(post_id, None)
        await message.answer("✅ <b>Кнопки удалены!</b>", parse_mode="HTML")
    else:
        # Проверяем формат кнопок
        keyboard = parse_url_buttons(message.text)
        if not keyboard:
            await message.answer(
                "⚠️ <b>Неверный формат кнопок</b>\n\n"
                "Используйте: <code>Текст - http://url</code>",
                parse_mode="HTML"
            )
            return
        
        await db.update_scheduled_post_buttons(post_id, message.text)
        await message.answer("✅ <b>Кнопки обновлены!</b>", parse_mode="HTML")
    
    await message.answer(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ])
    )
    await state.set_state(ScheduledStates.viewing)


@router.callback_query(F.data.startswith("sched_time_"))
async def change_scheduled_time(callback: CallbackQuery, state: FSMContext):
    """Изменение времени отложенного поста"""
    post_id = int(callback.data.split("_")[-1])
    
    await state.update_data(reschedule_post_id=post_id)
    
    now = get_moscow_now()
    
    await callback.message.edit_text(
        f"⏰ <b>Изменение времени публикации</b>\n\n"
        f"🕐 Сейчас по Москве: {now.strftime('%H:%M')}\n\n"
        f"Выберите новое время или введите вручную:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏱ +1 час", callback_data=f"resched_1h_{post_id}"),
                InlineKeyboardButton(text="⏱ +3 часа", callback_data=f"resched_3h_{post_id}")
            ],
            [
                InlineKeyboardButton(text="⏱ +6 часов", callback_data=f"resched_6h_{post_id}"),
                InlineKeyboardButton(text="🌅 Завтра 9:00", callback_data=f"resched_tomorrow_{post_id}")
            ],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"resched_custom_{post_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sched_view_{post_id}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("resched_"))
async def reschedule_preset(callback: CallbackQuery, state: FSMContext):
    """Перенос на предустановленное время"""
    parts = callback.data.split("_")
    preset = parts[1]
    post_id = int(parts[2])
    
    now = get_moscow_now()
    
    if preset == "1h":
        new_time = now + timedelta(hours=1)
    elif preset == "3h":
        new_time = now + timedelta(hours=3)
    elif preset == "6h":
        new_time = now + timedelta(hours=6)
    elif preset == "tomorrow":
        tomorrow = now + timedelta(days=1)
        new_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    elif preset == "custom":
        await callback.message.edit_text(
            "📅 <b>Введите новое время:</b>\n\n"
            "Формат: <code>ЧЧ ММ ДД ММ</code>\n"
            "Пример: <code>14 30 05 12</code> — 5 декабря в 14:30\n\n"
            f"🕐 Сейчас по Москве: {now.strftime('%H:%M')}",
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
        await callback.answer("Неизвестный вариант")
        return
    
    # Сохраняем как naive datetime для БД
    new_time_naive = new_time.replace(tzinfo=None)
    await db.update_scheduled_post_time(post_id, new_time_naive)
    
    time_str = new_time.strftime("%d.%m в %H:%M")
    
    await callback.message.edit_text(
        f"✅ <b>Время изменено!</b>\n\n"
        f"📅 Новое время: {time_str}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer("Время изменено!")


@router.message(ScheduledStates.reschedule, F.text)
async def reschedule_custom_time(message: Message, state: FSMContext):
    """Пользовательское время переноса"""
    data = await state.get_data()
    post_id = data.get('reschedule_post_id')
    
    if not post_id:
        await message.answer("Ошибка. Попробуйте снова.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 4:
            raise ValueError("Неверный формат")
        
        hour, minute, day, month = map(int, parts)
        year = get_moscow_now().year
        
        # Если месяц уже прошел - берем следующий год
        if month < get_moscow_now().month:
            year += 1
        
        new_time = datetime(year, month, day, hour, minute)
        
        if new_time <= datetime.now():
            await message.answer(
                "⚠️ <b>Время должно быть в будущем!</b>\n\n"
                "Попробуйте снова:",
                parse_mode="HTML"
            )
            return
        
        await db.update_scheduled_post_time(post_id, new_time)
        
        time_str = new_time.strftime("%d.%m в %H:%M")
        
        await message.answer(
            f"✅ <b>Время изменено!</b>\n\n"
            f"📅 Новое время: {time_str}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 К посту", callback_data=f"sched_view_{post_id}")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
        await state.set_state(ScheduledStates.viewing)
    
    except ValueError:
        await message.answer(
            "⚠️ <b>Неверный формат!</b>\n\n"
            "Используйте: <code>ЧЧ ММ ДД ММ</code>\n"
            "Пример: <code>14 30 05 12</code>",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("sched_publish_"))
async def publish_scheduled_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Опубликовать отложенный пост сейчас"""
    post_id = int(callback.data.split("_")[-1])
    post = await db.get_scheduled_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    # Публикуем
    settings = await db.get_user_settings(callback.from_user.id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    disable_notification = not settings['notifications'] if settings else True
    
    keyboard = None
    if post['buttons']:
        keyboard = parse_url_buttons(post['buttons'])
    
    try:
        if post['media_type'] == 'photo' and post['media_file_id']:
            msg = await bot.send_photo(
                chat_id=post['channel_id'],
                photo=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif post['media_type'] == 'video' and post['media_file_id']:
            msg = await bot.send_video(
                chat_id=post['channel_id'],
                video=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif post['media_type'] == 'document' and post['media_file_id']:
            msg = await bot.send_document(
                chat_id=post['channel_id'],
                document=post['media_file_id'],
                caption=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        else:
            msg = await bot.send_message(
                chat_id=post['channel_id'],
                text=post['text'],
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        
        # Обновляем статус
        await db.update_scheduled_post_status(post_id, 'published')
        await db.add_post_stats(post['channel_id'], msg.message_id)
        
        channel = await db.get_channel_by_id(post['channel_id'])
        username = channel['channel_username'] if channel else None
        
        if username:
            url = f"https://t.me/{username.lstrip('@')}/{msg.message_id}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Посмотреть", url=url)],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        
        await callback.message.edit_text(
            "✅ <b>Пост опубликован!</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации:</b>\n{e}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sched_view_{post_id}")]
            ])
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("sched_delete_"))
async def delete_scheduled_confirm(callback: CallbackQuery):
    """Подтверждение удаления"""
    post_id = int(callback.data.split("_")[-1])
    
    await callback.message.edit_text(
        "❓ <b>Удалить этот отложенный пост?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"sched_confirm_del_{post_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"sched_view_{post_id}")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_confirm_del_"))
async def delete_scheduled_post(callback: CallbackQuery, state: FSMContext):
    """Удаление отложенного поста"""
    post_id = int(callback.data.split("_")[-1])
    await db.delete_scheduled_post(post_id)
    
    await callback.message.edit_text(
        "🗑 <b>Пост удалён</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К списку", callback_data="sched_back_list")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ])
    )
    await callback.answer("Удалено!")


@router.callback_query(F.data == "sched_back_list")
async def back_to_scheduled_list(callback: CallbackQuery, state: FSMContext):
    """Вернуться к списку отложенных"""
    posts = await db.get_user_scheduled_posts(callback.from_user.id)
    
    if not posts:
        await callback.message.edit_text(
            "📅 <b>Отложенные посты</b>\n\n"
            "У вас нет запланированных публикаций.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return
    
    text = f"📅 <b>Отложенные посты ({len(posts)})</b>\n\n"
    
    buttons = []
    for post in posts[:10]:
        scheduled_time = parse_scheduled_time(post['scheduled_time'])
        time_str = scheduled_time.strftime("%d.%m в %H:%M")
        preview = (post['text'] or '[Медиа]')[:30]
        
        buttons.append([
            InlineKeyboardButton(
                text=f"📝 {time_str} — {preview[:15]}...",
                callback_data=f"sched_view_{post['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()
