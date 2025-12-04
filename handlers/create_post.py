from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
import asyncio
import pytz

from keyboards import (
    get_main_menu, get_cancel_keyboard, get_channels_keyboard,
    get_publish_keyboard, get_confirm_publish_keyboard, get_schedule_keyboard,
    get_delete_timer_keyboard, get_view_post_keyboard,
    parse_url_buttons, get_back_inline_keyboard
)
import database as db

router = Router()
logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_now():
    """Московское время без tzinfo"""
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)


class CreatePostStates(StatesGroup):
    select_channel = State()
    enter_text = State()
    constructor = State()
    add_media = State()
    add_buttons = State()
    add_album = State()
    preview = State()
    publish_menu = State()
    schedule_custom = State()
    delete_timer_custom = State()


def get_post_constructor_keyboard(has_text=False, has_media=False, has_buttons=False, has_album=False):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    
    if has_text:
        buttons.append([InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")])
    
    if has_album:
        buttons.append([
            InlineKeyboardButton(text=f"📸 Альбом ({has_album})", callback_data="view_album"),
            InlineKeyboardButton(text="🗑", callback_data="clear_album")
        ])
    elif has_media:
        buttons.append([
            InlineKeyboardButton(text="🖼 Изменить медиа", callback_data="edit_media"),
            InlineKeyboardButton(text="🗑", callback_data="remove_media")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🖼 Медиа", callback_data="add_media"),
            InlineKeyboardButton(text="📸 Альбом", callback_data="add_album")
        ])
    
    if has_buttons:
        buttons.append([
            InlineKeyboardButton(text="🔗 Кнопки ✓", callback_data="edit_buttons"),
            InlineKeyboardButton(text="🗑", callback_data="remove_buttons")
        ])
    else:
        buttons.append([InlineKeyboardButton(text="🔗 URL-кнопки", callback_data="add_buttons")])
    
    buttons.append([InlineKeyboardButton(text="👁 Превью", callback_data="preview")])
    buttons.append([InlineKeyboardButton(text="📤 Далее", callback_data="next_step")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_preview(message: Message, data: dict, bot: Bot, edit: bool = False):
    text = data.get('post_text', '')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons_text = data.get('buttons_text')
    album = data.get('album', [])
    
    keyboard = parse_url_buttons(buttons_text) if buttons_text else None
    settings = await db.get_user_settings(message.from_user.id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    
    try:
        if album:
            media_group = []
            for i, item in enumerate(album):
                if item['type'] == 'photo':
                    media = InputMediaPhoto(media=item['file_id'])
                else:
                    media = InputMediaVideo(media=item['file_id'])
                if i == 0 and text:
                    media.caption = text
                    media.parse_mode = parse_mode
                media_group.append(media)
            await message.answer_media_group(media=media_group)
            if keyboard:
                await message.answer("⬆️", reply_markup=keyboard)
            return True
        elif media_type == 'photo' and media_file_id:
            await message.answer_photo(photo=media_file_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode)
        elif media_type == 'video' and media_file_id:
            await message.answer_video(video=media_file_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode)
        elif media_type == 'document' and media_file_id:
            await message.answer_document(document=media_file_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode)
        elif text:
            await message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
        else:
            await message.answer("⚠️ Пост пуст")
            return False
        return True
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
        return False


async def publish_post(bot: Bot, channel_id: int, data: dict, user_id: int):
    text = data.get('post_text', '')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons_text = data.get('buttons_text')
    album = data.get('album', [])
    
    keyboard = parse_url_buttons(buttons_text) if buttons_text else None
    settings = await db.get_user_settings(user_id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    disable_notification = not settings['notifications'] if settings else True
    
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if album:
                media_group = []
                for i, item in enumerate(album):
                    if item['type'] == 'photo':
                        media = InputMediaPhoto(media=item['file_id'])
                    else:
                        media = InputMediaVideo(media=item['file_id'])
                    if i == 0 and text:
                        media.caption = text
                        media.parse_mode = parse_mode
                    media_group.append(media)
                messages = await bot.send_media_group(chat_id=channel_id, media=media_group, disable_notification=disable_notification)
                if keyboard:
                    await bot.send_message(chat_id=channel_id, text="⬆️", reply_markup=keyboard, disable_notification=disable_notification)
                msg = messages[0]
            elif media_type == 'photo' and media_file_id:
                msg = await bot.send_photo(chat_id=channel_id, photo=media_file_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode, disable_notification=disable_notification)
            elif media_type == 'video' and media_file_id:
                msg = await bot.send_video(chat_id=channel_id, video=media_file_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode, disable_notification=disable_notification)
            elif media_type == 'document' and media_file_id:
                msg = await bot.send_document(chat_id=channel_id, document=media_file_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode, disable_notification=disable_notification)
            else:
                msg = await bot.send_message(chat_id=channel_id, text=text, reply_markup=keyboard, parse_mode=parse_mode, disable_notification=disable_notification)
            
            await db.add_post_stats(channel_id, msg.message_id)
            return True, msg
            
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Попытка {attempt + 1}/{max_retries} публикации в {channel_id}: {e}")
            
            # Если бот кикнут - нет смысла повторять
            if "kicked" in last_error.lower() or "blocked" in last_error.lower():
                return False, f"Бот удалён из канала. Добавьте бота в админы заново."
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
    
    return False, last_error


# ============ СОЗДАНИЕ ПОСТА ============

@router.message(F.text == "✍️ Создать пост")
@router.message(Command("newpost"))
async def create_post_start(message: Message, state: FSMContext):
    await state.clear()
    channels = await db.get_channels(message.from_user.id)
    
    if not channels:
        await message.answer(
            "📢 <b>Нет каналов</b>\n\n"
            "1. Добавьте бота в канал как админа\n"
            "2. Перешлите сообщение из канала",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(CreatePostStates.select_channel)
        return
    
    if len(channels) == 1:
        await state.update_data(channel_id=channels[0]['channel_id'])
        await message.answer(
            f"📝 <b>Канал:</b> {channels[0]['channel_title'] or channels[0]['channel_username']}\n\nВведите текст:",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(CreatePostStates.enter_text)
    else:
        await message.answer("📢 <b>Выберите канал:</b>", parse_mode="HTML", reply_markup=get_channels_keyboard(channels))
        await state.set_state(CreatePostStates.select_channel)


@router.callback_query(CreatePostStates.select_channel, F.data.startswith("channel_select_"))
async def channel_selected(callback: CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[-1])
    channel = await db.get_channel_by_id(channel_id)
    await state.update_data(channel_id=channel_id)
    
    await callback.message.edit_text(f"📝 <b>Канал:</b> {channel['channel_title'] or channel['channel_username']}\n\nВведите текст:", parse_mode="HTML")
    await state.set_state(CreatePostStates.enter_text)
    await callback.answer()


@router.message(CreatePostStates.select_channel, F.forward_from_chat)
async def add_channel_from_forward(message: Message, state: FSMContext, bot: Bot):
    chat = message.forward_from_chat
    
    if chat.type not in ['channel']:
        await message.answer("⚠️ Это не канал")
        return
    
    # Retry логика для проверки прав (Telegram API иногда глючит)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            bot_member = await bot.get_chat_member(chat.id, bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Ждём и пробуем ещё
                    continue
                await message.answer("⚠️ Бот не админ канала. Добавьте бота в админы и попробуйте снова.")
                return
            if not getattr(bot_member, 'can_post_messages', False):
                await message.answer("⚠️ Нет прав на публикацию. Включите право 'Публикация сообщений' для бота.")
                return
            
            user_member = await bot.get_chat_member(chat.id, message.from_user.id)
            if user_member.status not in ['creator', 'administrator']:
                await message.answer("⚠️ Вы не админ канала")
                return
            
            # Всё ок, выходим из цикла
            break
            
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            logger.error(f"Ошибка проверки прав канала {chat.id}: {e}")
            await message.answer(f"⚠️ Ошибка проверки прав. Попробуйте ещё раз через пару секунд.")
            return
    
    await db.add_channel(channel_id=chat.id, username=chat.username, title=chat.title, added_by=message.from_user.id)
    await state.update_data(channel_id=chat.id)
    
    await message.answer(f"✅ Канал <b>{chat.title}</b> добавлен!\n\nВведите текст:", parse_mode="HTML", reply_markup=get_cancel_keyboard())
    await state.set_state(CreatePostStates.enter_text)


@router.message(CreatePostStates.enter_text, F.text)
async def post_text_received(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    
    await state.update_data(post_text=message.text)
    data = await state.get_data()
    
    await message.answer("✅ Текст добавлен!", reply_markup=get_post_constructor_keyboard(
        has_text=True,
        has_media=data.get('media_file_id') is not None,
        has_buttons=data.get('buttons_text') is not None,
        has_album=len(data.get('album', [])) if data.get('album') else False
    ))
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.enter_text, F.photo)
async def post_photo_as_text(message: Message, state: FSMContext):
    await state.update_data(media_type='photo', media_file_id=message.photo[-1].file_id, post_text=message.caption or '')
    data = await state.get_data()
    await message.answer("✅ Фото добавлено!", reply_markup=get_post_constructor_keyboard(has_text=bool(message.caption), has_media=True, has_buttons=data.get('buttons_text') is not None))
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.enter_text, F.video)
async def post_video_as_text(message: Message, state: FSMContext):
    await state.update_data(media_type='video', media_file_id=message.video.file_id, post_text=message.caption or '')
    data = await state.get_data()
    await message.answer("✅ Видео добавлено!", reply_markup=get_post_constructor_keyboard(has_text=bool(message.caption), has_media=True, has_buttons=data.get('buttons_text') is not None))
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.enter_text, F.document)
async def post_doc_as_text(message: Message, state: FSMContext):
    await state.update_data(media_type='document', media_file_id=message.document.file_id, post_text=message.caption or '')
    data = await state.get_data()
    await message.answer("✅ Документ добавлен!", reply_markup=get_post_constructor_keyboard(has_text=bool(message.caption), has_media=True, has_buttons=data.get('buttons_text') is not None))
    await state.set_state(CreatePostStates.constructor)


# ============ КОНСТРУКТОР ============

@router.callback_query(CreatePostStates.constructor, F.data == "edit_text")
async def edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новый текст:")
    await state.set_state(CreatePostStates.enter_text)
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data.in_(["add_media", "edit_media"]))
async def add_media(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🖼 Отправьте фото/видео/документ:", reply_markup=get_back_inline_keyboard("back_to_constructor"))
    await state.set_state(CreatePostStates.add_media)
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "add_album")
async def add_album_start(callback: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await state.update_data(album=[], media_type=None, media_file_id=None)
    await callback.message.edit_text("📸 <b>Альбом</b>\n\nОтправляйте фото/видео (макс 10)\n\n📎 0/10", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="finish_album")]]))
    await state.set_state(CreatePostStates.add_album)
    await callback.answer()


@router.message(CreatePostStates.add_album, F.photo)
async def album_photo(message: Message, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    data = await state.get_data()
    album = data.get('album', [])
    if len(album) >= 10:
        await message.answer("⚠️ Максимум 10!")
        return
    album.append({'type': 'photo', 'file_id': message.photo[-1].file_id})
    await state.update_data(album=album)
    await message.answer(f"✅ Фото добавлено! 📎 {len(album)}/10", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ Готово ({len(album)})", callback_data="finish_album")]]))


@router.message(CreatePostStates.add_album, F.video)
async def album_video(message: Message, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    data = await state.get_data()
    album = data.get('album', [])
    if len(album) >= 10:
        await message.answer("⚠️ Максимум 10!")
        return
    album.append({'type': 'video', 'file_id': message.video.file_id})
    await state.update_data(album=album)
    await message.answer(f"✅ Видео добавлено! 📎 {len(album)}/10", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ Готово ({len(album)})", callback_data="finish_album")]]))


@router.callback_query(F.data == "finish_album")
async def finish_album(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    album = data.get('album', [])
    await callback.message.edit_text(f"✅ Альбом: {len(album)} файлов" if album else "📝 Альбом пуст", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=False, has_buttons=data.get('buttons_text') is not None, has_album=len(album) if album else False))
    await state.set_state(CreatePostStates.constructor)
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "clear_album")
async def clear_album(callback: CallbackQuery, state: FSMContext):
    await state.update_data(album=[])
    data = await state.get_data()
    await callback.message.edit_text("🗑 Альбом очищен", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=False, has_buttons=data.get('buttons_text') is not None))
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "view_album")
async def view_album(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    album = data.get('album', [])
    if not album:
        await callback.answer("Пусто")
        return
    media_group = []
    for item in album:
        if item['type'] == 'photo':
            media_group.append(InputMediaPhoto(media=item['file_id']))
        else:
            media_group.append(InputMediaVideo(media=item['file_id']))
    await callback.message.answer_media_group(media=media_group)
    await callback.answer()


@router.message(CreatePostStates.add_media, F.photo)
async def media_photo(message: Message, state: FSMContext):
    await state.update_data(media_type='photo', media_file_id=message.photo[-1].file_id)
    data = await state.get_data()
    await message.answer("✅ Фото!", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=True, has_buttons=data.get('buttons_text') is not None))
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.add_media, F.video)
async def media_video(message: Message, state: FSMContext):
    await state.update_data(media_type='video', media_file_id=message.video.file_id)
    data = await state.get_data()
    await message.answer("✅ Видео!", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=True, has_buttons=data.get('buttons_text') is not None))
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.add_media, F.document)
async def media_doc(message: Message, state: FSMContext):
    await state.update_data(media_type='document', media_file_id=message.document.file_id)
    data = await state.get_data()
    await message.answer("✅ Документ!", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=True, has_buttons=data.get('buttons_text') is not None))
    await state.set_state(CreatePostStates.constructor)


@router.callback_query(CreatePostStates.constructor, F.data == "remove_media")
async def remove_media(callback: CallbackQuery, state: FSMContext):
    await state.update_data(media_type=None, media_file_id=None)
    data = await state.get_data()
    await callback.message.edit_text("🗑 Удалено", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=False, has_buttons=data.get('buttons_text') is not None))
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data.in_(["add_buttons", "edit_buttons"]))
async def add_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔗 <b>URL-кнопки</b>\n\nФормат:\n<code>Кнопка - http://url</code>\n\nРазделитель <code>|</code> для ряда", parse_mode="HTML", reply_markup=get_back_inline_keyboard("back_to_constructor"))
    await state.set_state(CreatePostStates.add_buttons)
    await callback.answer()


@router.message(CreatePostStates.add_buttons, F.text)
async def buttons_received(message: Message, state: FSMContext):
    keyboard = parse_url_buttons(message.text)
    if not keyboard:
        await message.answer("⚠️ Формат: <code>Кнопка - http://url</code>", parse_mode="HTML", reply_markup=get_back_inline_keyboard("back_to_constructor"))
        return
    await state.update_data(buttons_text=message.text)
    data = await state.get_data()
    album = data.get('album', [])
    await message.answer("✅ Кнопки!", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=data.get('media_file_id') is not None, has_buttons=True, has_album=len(album) if album else False))
    await state.set_state(CreatePostStates.constructor)


@router.callback_query(CreatePostStates.constructor, F.data == "remove_buttons")
async def remove_buttons(callback: CallbackQuery, state: FSMContext):
    await state.update_data(buttons_text=None)
    data = await state.get_data()
    album = data.get('album', [])
    await callback.message.edit_text("🗑 Кнопки удалены", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=data.get('media_file_id') is not None, has_buttons=False, has_album=len(album) if album else False))
    await callback.answer()


@router.callback_query(F.data == "back_to_constructor")
async def back_to_constructor(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    album = data.get('album', [])
    await callback.message.edit_text("📝 Конструктор", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=data.get('media_file_id') is not None, has_buttons=data.get('buttons_text') is not None, has_album=len(album) if album else False))
    await state.set_state(CreatePostStates.constructor)
    await callback.answer()


# ============ ПРЕВЬЮ И ПУБЛИКАЦИЯ ============

@router.callback_query(CreatePostStates.constructor, F.data == "preview")
async def preview_post(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data.get('post_text') and not data.get('media_file_id') and not data.get('album'):
        await callback.answer("⚠️ Пост пуст", show_alert=True)
        return
    await callback.message.delete()
    await send_preview(callback.message, data, bot)
    album = data.get('album', [])
    await callback.message.answer("⬆️ Превью", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=data.get('media_file_id') is not None, has_buttons=data.get('buttons_text') is not None, has_album=len(album) if album else False))
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "next_step")
async def next_step(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data.get('post_text') and not data.get('media_file_id') and not data.get('album'):
        await callback.answer("⚠️ Пост пуст", show_alert=True)
        return
    await callback.message.delete()
    await send_preview(callback.message, data, bot)
    await callback.message.answer("📤 <b>Готово!</b>", parse_mode="HTML", reply_markup=get_publish_keyboard())
    await state.set_state(CreatePostStates.publish_menu)
    await callback.answer()


@router.callback_query(F.data == "cancel_post")
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Отменено", reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "back_to_edit")
async def back_to_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    album = data.get('album', [])
    await callback.message.edit_text("📝 Конструктор", reply_markup=get_post_constructor_keyboard(has_text=bool(data.get('post_text')), has_media=data.get('media_file_id') is not None, has_buttons=data.get('buttons_text') is not None, has_album=len(album) if album else False))
    await state.set_state(CreatePostStates.constructor)
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "publish_now")
async def publish_now(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❓ Опубликовать?", reply_markup=get_confirm_publish_keyboard())
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "back_to_publish_menu")
async def back_to_publish_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 <b>Готово!</b>", parse_mode="HTML", reply_markup=get_publish_keyboard())
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "confirm_publish")
async def confirm_publish(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    channel_id = data.get('channel_id')
    success, result = await publish_post(bot, channel_id, data, callback.from_user.id)
    if success:
        channel = await db.get_channel_by_id(channel_id)
        username = channel['channel_username'] if channel else None
        await state.clear()
        await callback.message.edit_text("✅ Опубликовано!", reply_markup=get_view_post_keyboard(username, result.message_id))
    else:
        await callback.message.edit_text(f"❌ Ошибка: {result}", reply_markup=get_back_inline_keyboard("back_to_publish_menu"))
    await callback.answer()


# ============ ОТЛОЖЕННАЯ ПУБЛИКАЦИЯ (МОСКОВСКОЕ ВРЕМЯ) ============

@router.callback_query(CreatePostStates.publish_menu, F.data == "schedule_post")
async def schedule_menu(callback: CallbackQuery, state: FSMContext):
    now = get_moscow_now()
    await callback.message.edit_text(
        f"⏰ <b>Отложенная публикация</b>\n\n🕐 Сейчас: <b>{now.strftime('%H:%M')}</b> МСК",
        parse_mode="HTML",
        reply_markup=get_schedule_keyboard()
    )
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data.startswith("schedule_"))
async def schedule_preset(callback: CallbackQuery, state: FSMContext):
    preset = callback.data.replace("schedule_", "")
    now = get_moscow_now()
    
    if preset == "1h":
        scheduled = now + timedelta(hours=1)
    elif preset == "3h":
        scheduled = now + timedelta(hours=3)
    elif preset == "6h":
        scheduled = now + timedelta(hours=6)
    elif preset == "tomorrow":
        tomorrow = now + timedelta(days=1)
        scheduled = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    elif preset == "custom":
        await callback.message.edit_text(
            f"📅 <b>Введите время (МСК):</b>\n\n"
            f"Формат: <code>ЧЧ ММ ДД ММ</code>\n"
            f"Пример: <code>14 00 05 12</code> = 5 дек 14:00\n\n"
            f"🕐 Сейчас: {now.strftime('%H:%M')} МСК",
            parse_mode="HTML",
            reply_markup=get_back_inline_keyboard("back_to_publish_menu")
        )
        await state.set_state(CreatePostStates.schedule_custom)
        await callback.answer()
        return
    else:
        await callback.answer("Ошибка")
        return
    
    data = await state.get_data()
    
    await db.add_scheduled_post(
        channel_id=data.get('channel_id'),
        user_id=callback.from_user.id,
        text=data.get('post_text', ''),
        media_type=data.get('media_type'),
        media_file_id=data.get('media_file_id'),
        buttons=data.get('buttons_text'),
        scheduled_time=scheduled,
        delete_after=data.get('delete_after')
    )
    
    await state.clear()
    await callback.message.edit_text(f"⏰ <b>Отложено!</b>\n\n📅 {scheduled.strftime('%d.%m в %H:%M')} МСК", parse_mode="HTML")
    await callback.message.answer("🏠 Меню", reply_markup=get_main_menu())
    await callback.answer()


@router.message(CreatePostStates.schedule_custom, F.text)
async def schedule_custom(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().split()
        if len(parts) != 4:
            raise ValueError()
        
        hour, minute, day, month = map(int, parts)
        now = get_moscow_now()
        year = now.year
        
        if month < now.month or (month == now.month and day < now.day):
            year += 1
        
        scheduled = datetime(year, month, day, hour, minute)
        
        if scheduled <= now:
            await message.answer("⚠️ Время в будущем!")
            return
        
        data = await state.get_data()
        
        await db.add_scheduled_post(
            channel_id=data.get('channel_id'),
            user_id=message.from_user.id,
            text=data.get('post_text', ''),
            media_type=data.get('media_type'),
            media_file_id=data.get('media_file_id'),
            buttons=data.get('buttons_text'),
            scheduled_time=scheduled,
            delete_after=data.get('delete_after')
        )
        
        await state.clear()
        await message.answer(f"⏰ <b>Отложено!</b>\n\n📅 {scheduled.strftime('%d.%m в %H:%M')} МСК", parse_mode="HTML", reply_markup=get_main_menu())
    
    except ValueError:
        await message.answer("⚠️ Формат: <code>ЧЧ ММ ДД ММ</code>", parse_mode="HTML")


# ============ ТАЙМЕР УДАЛЕНИЯ ============

@router.callback_query(CreatePostStates.publish_menu, F.data == "set_delete_timer")
async def delete_timer_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⏱ <b>Таймер удаления</b>", parse_mode="HTML", reply_markup=get_delete_timer_keyboard())
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data.startswith("delete_"))
async def delete_timer_preset(callback: CallbackQuery, state: FSMContext):
    preset = callback.data.replace("delete_", "")
    
    timers = {"1h": 3600, "6h": 21600, "12h": 43200, "24h": 86400}
    
    if preset in timers:
        await state.update_data(delete_after=timers[preset])
        hours = timers[preset] // 3600
        await callback.message.edit_text(f"✅ Таймер: {hours}ч", reply_markup=get_publish_keyboard())
    elif preset == "custom":
        await callback.message.edit_text("⏱ Введите минуты:", reply_markup=get_back_inline_keyboard("back_to_publish_menu"))
        await state.set_state(CreatePostStates.delete_timer_custom)
    
    await callback.answer()


@router.message(CreatePostStates.delete_timer_custom, F.text)
async def delete_timer_custom(message: Message, state: FSMContext):
    try:
        minutes = int(message.text.strip())
        if minutes <= 0:
            raise ValueError()
        await state.update_data(delete_after=minutes * 60)
        await message.answer(f"✅ Таймер: {minutes} мин", reply_markup=get_publish_keyboard())
        await state.set_state(CreatePostStates.publish_menu)
    except ValueError:
        await message.answer("⚠️ Введите число минут")


@router.callback_query(F.data == "add_channel")
@router.message(Command("addchannel"))
async def add_channel_cmd(update, state: FSMContext):
    text = "📢 <b>Добавление канала</b>\n\n1. Добавьте бота админом\n2. Перешлите сообщение из канала"
    if isinstance(update, CallbackQuery):
        await update.message.edit_text(text, parse_mode="HTML")
        await update.answer()
    else:
        await update.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    await state.set_state(CreatePostStates.select_channel)
