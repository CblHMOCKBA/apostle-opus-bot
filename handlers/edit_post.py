from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import (
    get_main_menu, get_cancel_keyboard, get_channels_keyboard,
    parse_url_buttons, get_back_inline_keyboard
)
import database as db

router = Router()


class EditPostStates(StatesGroup):
    """Состояния для редактирования поста"""
    select_channel = State()
    forward_message = State()
    editing = State()
    edit_text = State()
    edit_buttons = State()
    edit_media = State()


def get_edit_keyboard(has_media: bool = False, has_buttons: bool = False):
    """Клавиатура редактирования поста"""
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_post_text")]
    ]
    
    if has_media:
        buttons.append([
            InlineKeyboardButton(text="🖼 Изменить медиа", callback_data="edit_post_media"),
            InlineKeyboardButton(text="🗑 Удалить медиа", callback_data="remove_post_media")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🖼 Добавить медиа", callback_data="edit_post_media")
        ])
    
    if has_buttons:
        buttons.append([
            InlineKeyboardButton(text="🔗 Изменить кнопки", callback_data="edit_post_buttons"),
            InlineKeyboardButton(text="🗑 Удалить кнопки", callback_data="remove_post_buttons")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🔗 Добавить кнопки", callback_data="edit_post_buttons")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🔄 Копировать пост", callback_data="copy_post")
    ])
    buttons.append([
        InlineKeyboardButton(text="💾 Сохранить изменения", callback_data="save_post_changes")
    ])
    buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_post")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "✏️ Редактировать")
async def edit_post_start(message: Message, state: FSMContext):
    """Начало редактирования поста"""
    await state.clear()
    
    channels = await db.get_channels(message.from_user.id)
    
    if not channels:
        await message.answer(
            "📢 <b>У вас нет подключенных каналов</b>\n\n"
            "Сначала добавьте канал через меню создания поста.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
    
    if len(channels) == 1:
        await state.update_data(channel_id=channels[0]['channel_id'])
        await message.answer(
            "✏️ <b>Редактирование поста</b>\n\n"
            "Перешлите мне сообщение из канала, которое хотите отредактировать.",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(EditPostStates.forward_message)
    else:
        await message.answer(
            "📢 <b>Выберите канал:</b>",
            parse_mode="HTML",
            reply_markup=get_channels_keyboard(channels, action="edit")
        )
        await state.set_state(EditPostStates.select_channel)


@router.callback_query(EditPostStates.select_channel, F.data.startswith("channel_edit_"))
async def edit_channel_selected(callback: CallbackQuery, state: FSMContext):
    """Канал выбран для редактирования"""
    channel_id = int(callback.data.split("_")[-1])
    await state.update_data(channel_id=channel_id)
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование поста</b>\n\n"
        "Перешлите мне сообщение из канала, которое хотите отредактировать.",
        parse_mode="HTML"
    )
    await state.set_state(EditPostStates.forward_message)
    await callback.answer()


@router.message(EditPostStates.forward_message, F.forward_from_chat)
async def forwarded_message_received(message: Message, state: FSMContext, bot: Bot):
    """Получено пересланное сообщение"""
    data = await state.get_data()
    forward_chat = message.forward_from_chat
    
    if not forward_chat:
        await message.answer(
            "⚠️ <b>Перешлите сообщение из канала</b>",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, что это сообщение из правильного канала
    channel_id = data.get('channel_id')
    if channel_id and forward_chat.id != channel_id:
        await message.answer(
            "⚠️ <b>Это сообщение из другого канала</b>\n\n"
            "Перешлите сообщение из выбранного канала.",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем данные сообщения
    original_message_id = message.forward_from_message_id
    
    await state.update_data(
        channel_id=forward_chat.id,
        message_id=original_message_id,
        original_text=message.text or message.caption or '',
        has_media=bool(message.photo or message.video or message.document),
        media_type='photo' if message.photo else ('video' if message.video else ('document' if message.document else None)),
        media_file_id=message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else (message.document.file_id if message.document else None))
    )
    
    has_media = bool(message.photo or message.video or message.document)
    has_buttons = bool(message.reply_markup)
    
    await message.answer(
        f"✏️ <b>Редактирование сообщения #{original_message_id}</b>\n\n"
        f"📝 Текст: <i>{(message.text or message.caption or '[Без текста]')[:100]}...</i>\n\n"
        "Выберите, что хотите изменить:",
        parse_mode="HTML",
        reply_markup=get_edit_keyboard(has_media=has_media, has_buttons=has_buttons)
    )
    await state.set_state(EditPostStates.editing)


@router.callback_query(EditPostStates.editing, F.data == "edit_post_text")
async def edit_text_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования текста"""
    data = await state.get_data()
    current_text = data.get('original_text', '')
    
    await callback.message.edit_text(
        f"✏️ <b>Текущий текст:</b>\n\n"
        f"<i>{current_text[:500]}{'...' if len(current_text) > 500 else ''}</i>\n\n"
        "Введите новый текст:",
        parse_mode="HTML",
        reply_markup=get_back_inline_keyboard("back_to_edit_menu")
    )
    await state.set_state(EditPostStates.edit_text)
    await callback.answer()


@router.message(EditPostStates.edit_text, F.text)
async def new_text_received(message: Message, state: FSMContext):
    """Получен новый текст"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    
    await state.update_data(new_text=message.text)
    
    data = await state.get_data()
    has_media = data.get('has_media', False)
    
    await message.answer(
        "✅ <b>Текст изменен!</b>\n\n"
        "Продолжите редактирование или сохраните изменения:",
        parse_mode="HTML",
        reply_markup=get_edit_keyboard(has_media=has_media, has_buttons=False)
    )
    await state.set_state(EditPostStates.editing)


@router.callback_query(EditPostStates.editing, F.data == "edit_post_buttons")
async def edit_buttons_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования кнопок"""
    await callback.message.edit_text(
        "🔗 <b>Введите новые URL-кнопки:</b>\n\n"
        "Формат: <code>Кнопка - http://url</code>\n"
        "Разделитель <code>|</code> для горизонтального размещения",
        parse_mode="HTML",
        reply_markup=get_back_inline_keyboard("back_to_edit_menu")
    )
    await state.set_state(EditPostStates.edit_buttons)
    await callback.answer()


@router.message(EditPostStates.edit_buttons, F.text)
async def new_buttons_received(message: Message, state: FSMContext):
    """Получены новые кнопки"""
    keyboard = parse_url_buttons(message.text)
    
    if not keyboard:
        await message.answer(
            "⚠️ <b>Не удалось распознать кнопки</b>\n\n"
            "Проверьте формат: <code>Кнопка - http://url</code>",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(new_buttons=message.text)
    
    data = await state.get_data()
    has_media = data.get('has_media', False)
    
    await message.answer(
        "✅ <b>Кнопки изменены!</b>\n\n"
        "Продолжите редактирование или сохраните изменения:",
        parse_mode="HTML",
        reply_markup=get_edit_keyboard(has_media=has_media, has_buttons=True)
    )
    await state.set_state(EditPostStates.editing)


@router.callback_query(EditPostStates.editing, F.data == "remove_post_buttons")
async def remove_post_buttons(callback: CallbackQuery, state: FSMContext):
    """Удаление кнопок"""
    await state.update_data(new_buttons=None, remove_buttons=True)
    
    data = await state.get_data()
    has_media = data.get('has_media', False)
    
    await callback.message.edit_text(
        "🗑 <b>Кнопки будут удалены</b>\n\n"
        "Сохраните изменения для применения:",
        parse_mode="HTML",
        reply_markup=get_edit_keyboard(has_media=has_media, has_buttons=False)
    )
    await callback.answer("Кнопки будут удалены")


@router.callback_query(F.data == "back_to_edit_menu")
async def back_to_edit_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню редактирования"""
    data = await state.get_data()
    has_media = data.get('has_media', False)
    has_buttons = bool(data.get('new_buttons'))
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование поста</b>\n\n"
        "Выберите, что хотите изменить:",
        parse_mode="HTML",
        reply_markup=get_edit_keyboard(has_media=has_media, has_buttons=has_buttons)
    )
    await state.set_state(EditPostStates.editing)
    await callback.answer()


# ============ КОПИРОВАНИЕ ПОСТА ============

@router.callback_query(EditPostStates.editing, F.data == "copy_post")
async def copy_post(callback: CallbackQuery, state: FSMContext):
    """Копирование поста для создания нового"""
    data = await state.get_data()
    
    # Получаем каналы для выбора
    channels = await db.get_channels(callback.from_user.id)
    
    if len(channels) == 1:
        # Сразу копируем в тот же канал
        await state.update_data(copy_channel_id=channels[0]['channel_id'])
        await show_copy_options(callback, state)
    else:
        # Выбор канала
        buttons = []
        for ch in channels:
            title = ch['channel_title'] or ch['channel_username']
            buttons.append([
                InlineKeyboardButton(text=f"📢 {title}", callback_data=f"copy_to_channel_{ch['channel_id']}")
            ])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_edit_menu")])
        
        await callback.message.edit_text(
            "🔄 <b>Копирование поста</b>\n\n"
            "Выберите канал для публикации копии:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    
    await callback.answer()


@router.callback_query(EditPostStates.editing, F.data.startswith("copy_to_channel_"))
async def copy_channel_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран канал для копии"""
    channel_id = int(callback.data.split("_")[-1])
    await state.update_data(copy_channel_id=channel_id)
    await show_copy_options(callback, state)


async def show_copy_options(callback: CallbackQuery, state: FSMContext):
    """Показать опции копирования"""
    await callback.message.edit_text(
        "🔄 <b>Копирование поста</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Опубликовать копию сейчас", callback_data="publish_copy_now")],
            [InlineKeyboardButton(text="✏️ Редактировать перед публикацией", callback_data="edit_copy")],
            [InlineKeyboardButton(text="📋 Сохранить как шаблон", callback_data="save_as_template")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_edit_menu")]
        ])
    )
    await callback.answer()


@router.callback_query(EditPostStates.editing, F.data == "publish_copy_now")
async def publish_copy_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Опубликовать копию сейчас"""
    data = await state.get_data()
    channel_id = data.get('copy_channel_id', data.get('channel_id'))
    
    text = data.get('new_text', data.get('original_text', ''))
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons_text = data.get('new_buttons')
    
    keyboard = None
    if buttons_text:
        keyboard = parse_url_buttons(buttons_text)
    
    settings = await db.get_user_settings(callback.from_user.id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    disable_notification = not settings['notifications'] if settings else True
    
    try:
        if media_type == 'photo' and media_file_id:
            msg = await bot.send_photo(
                chat_id=channel_id,
                photo=media_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif media_type == 'video' and media_file_id:
            msg = await bot.send_video(
                chat_id=channel_id,
                video=media_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        elif media_type == 'document' and media_file_id:
            msg = await bot.send_document(
                chat_id=channel_id,
                document=media_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        else:
            msg = await bot.send_message(
                chat_id=channel_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        
        await db.add_post_stats(channel_id, msg.message_id)
        
        channel = await db.get_channel_by_id(channel_id)
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
        
        await state.clear()
        await callback.message.edit_text(
            "✅ <b>Копия поста опубликована!</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b>\n{e}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_edit_menu")]
            ])
        )
    
    await callback.answer()


@router.callback_query(EditPostStates.editing, F.data == "edit_copy")
async def edit_copy(callback: CallbackQuery, state: FSMContext):
    """Редактировать копию перед публикацией"""
    from handlers.create_post import CreatePostStates, get_post_constructor_keyboard
    
    data = await state.get_data()
    
    # Переносим данные в формат create_post
    await state.update_data(
        post_text=data.get('new_text', data.get('original_text', '')),
        channel_id=data.get('copy_channel_id', data.get('channel_id'))
    )
    
    has_text = bool(data.get('original_text'))
    has_media = data.get('has_media', False)
    has_buttons = bool(data.get('new_buttons'))
    
    await callback.message.edit_text(
        "📝 <b>Редактирование копии</b>\n\n"
        "Измените нужные элементы:",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=has_media,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)
    await callback.answer()


@router.callback_query(EditPostStates.editing, F.data == "save_as_template")
async def save_as_template(callback: CallbackQuery, state: FSMContext):
    """Сохранить как шаблон"""
    from handlers.templates import TemplateStates
    
    data = await state.get_data()
    
    await state.update_data(
        template_text=data.get('new_text', data.get('original_text', '')),
        waiting_content=False
    )
    
    await callback.message.edit_text(
        "📋 <b>Сохранение как шаблон</b>\n\n"
        "Введите название для шаблона:",
        parse_mode="HTML",
        reply_markup=get_back_inline_keyboard("back_to_edit_menu")
    )
    await state.set_state(TemplateStates.enter_name)
    await callback.answer()


# ============ Сохранение изменений ============

@router.callback_query(EditPostStates.editing, F.data == "save_post_changes")
async def save_post_changes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Сохранение изменений"""
    data = await state.get_data()
    
    channel_id = data.get('channel_id')
    message_id = data.get('message_id')
    new_text = data.get('new_text', data.get('original_text', ''))
    new_buttons = data.get('new_buttons')
    remove_buttons = data.get('remove_buttons', False)
    has_media = data.get('has_media', False)
    
    settings = await db.get_user_settings(callback.from_user.id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    
    keyboard = None
    if new_buttons and not remove_buttons:
        keyboard = parse_url_buttons(new_buttons)
    
    try:
        if has_media:
            # Редактируем caption
            await bot.edit_message_caption(
                chat_id=channel_id,
                message_id=message_id,
                caption=new_text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        else:
            # Редактируем текст
            await bot.edit_message_text(
                chat_id=channel_id,
                message_id=message_id,
                text=new_text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        
        await state.clear()
        
        channel = await db.get_channel_by_id(channel_id)
        channel_username = channel['channel_username'] if channel else None
        
        if channel_username:
            url = f"https://t.me/{channel_username.lstrip('@')}/{message_id}"
            view_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Посмотреть изменения", url=url)],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        else:
            view_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        
        await callback.message.edit_text(
            "✅ <b>Изменения сохранены!</b>",
            parse_mode="HTML",
            reply_markup=view_button
        )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при сохранении:</b>\n{e}",
            parse_mode="HTML",
            reply_markup=get_back_inline_keyboard("back_to_edit_menu")
        )
    
    await callback.answer()


@router.callback_query(EditPostStates.editing, F.data == "cancel_edit_post")
async def cancel_edit_post(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "❌ Редактирование отменено",
        reply_markup=get_main_menu()
    )
    await callback.answer()
