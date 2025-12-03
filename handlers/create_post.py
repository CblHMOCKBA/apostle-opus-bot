from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import json
import logging

from keyboards import (
    get_main_menu, get_cancel_keyboard, get_channels_keyboard,
    get_post_constructor_keyboard, get_publish_keyboard,
    get_confirm_publish_keyboard, get_schedule_keyboard,
    get_delete_timer_keyboard, get_view_post_keyboard,
    parse_url_buttons, get_back_inline_keyboard
)
import database as db

router = Router()
logger = logging.getLogger(__name__)


class CreatePostStates(StatesGroup):
    """Состояния FSM для создания поста"""
    select_channel = State()
    enter_text = State()
    constructor = State()
    add_media = State()
    add_buttons = State()
    preview = State()
    publish_menu = State()
    schedule_custom = State()
    delete_timer_custom = State()


def get_post_data(data: dict) -> dict:
    """Получить данные поста из FSM"""
    return {
        'channel_id': data.get('channel_id'),
        'text': data.get('post_text', ''),
        'media_type': data.get('media_type'),
        'media_file_id': data.get('media_file_id'),
        'buttons': data.get('buttons_text'),
        'delete_after': data.get('delete_after')
    }


async def send_post_preview(message: Message, data: dict, bot: Bot, edit: bool = False):
    """Отправить предпросмотр поста"""
    text = data.get('post_text', '')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons_text = data.get('buttons_text')
    
    # Парсим кнопки
    keyboard = None
    if buttons_text:
        keyboard = parse_url_buttons(buttons_text)
    
    settings = await db.get_user_settings(message.from_user.id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    disable_notification = not settings['notifications'] if settings else True
    disable_web_page_preview = not settings['link_preview'] if settings else False
    
    try:
        if media_type == 'photo' and media_file_id:
            if edit:
                await message.edit_text("👁 <b>Предпросмотр:</b>", parse_mode="HTML")
            await message.answer_photo(
                photo=media_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        elif media_type == 'video' and media_file_id:
            if edit:
                await message.edit_text("👁 <b>Предпросмотр:</b>", parse_mode="HTML")
            await message.answer_video(
                video=media_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        elif media_type == 'document' and media_file_id:
            if edit:
                await message.edit_text("👁 <b>Предпросмотр:</b>", parse_mode="HTML")
            await message.answer_document(
                document=media_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        else:
            if text:
                if edit:
                    await message.edit_text(
                        f"👁 <b>Предпросмотр:</b>\n\n{text}",
                        reply_markup=keyboard,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
                else:
                    await message.answer(
                        f"👁 <b>Предпросмотр:</b>\n\n{text}",
                        reply_markup=keyboard,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
            else:
                await message.answer("⚠️ Пост пуст. Добавьте текст или медиафайл.")
                return False
        return True
    except Exception as e:
        logger.error(f"Preview error: {e}")
        await message.answer(f"⚠️ Ошибка форматирования: {e}")
        return False


async def publish_post(bot: Bot, channel_id: int, data: dict, user_id: int) -> tuple:
    """Опубликовать пост в канал"""
    text = data.get('post_text', '')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons_text = data.get('buttons_text')
    delete_after = data.get('delete_after')
    
    # Парсим кнопки
    keyboard = None
    if buttons_text:
        keyboard = parse_url_buttons(buttons_text)
    
    settings = await db.get_user_settings(user_id)
    parse_mode = settings['formatting'] if settings else 'HTML'
    disable_notification = not settings['notifications'] if settings else True
    disable_web_page_preview = not settings['link_preview'] if settings else False
    
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
                disable_notification=disable_notification,
                disable_web_page_preview=disable_web_page_preview
            )
        
        # Добавляем статистику
        await db.add_post_stats(channel_id, msg.message_id)
        
        return True, msg
    except Exception as e:
        logger.error(f"Publish error: {e}")
        return False, str(e)


# ============ Создание поста ============

@router.message(F.text == "✍️ Создать пост")
@router.message(Command("newpost"))
async def create_post_start(message: Message, state: FSMContext):
    """Начало создания поста"""
    await state.clear()
    
    # Получаем каналы пользователя
    channels = await db.get_channels(message.from_user.id)
    
    if not channels:
        await message.answer(
            "📢 <b>У вас нет подключенных каналов</b>\n\n"
            "Чтобы добавить канал:\n"
            "1. Добавьте бота в канал как администратора\n"
            "2. Перешлите мне любое сообщение из канала\n\n"
            "Или используйте команду /addchannel",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(CreatePostStates.select_channel)
        return
    
    if len(channels) == 1:
        # Если только один канал - сразу выбираем его
        await state.update_data(channel_id=channels[0]['channel_id'])
        await message.answer(
            f"📝 <b>Создание поста для канала:</b>\n"
            f"📢 {channels[0]['channel_title'] or channels[0]['channel_username']}\n\n"
            "Введите текст поста (поддерживается HTML форматирование):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(CreatePostStates.enter_text)
    else:
        # Выбор канала
        await message.answer(
            "📢 <b>Выберите канал для публикации:</b>",
            parse_mode="HTML",
            reply_markup=get_channels_keyboard(channels)
        )
        await state.set_state(CreatePostStates.select_channel)


@router.callback_query(CreatePostStates.select_channel, F.data.startswith("channel_select_"))
async def channel_selected(callback: CallbackQuery, state: FSMContext):
    """Канал выбран"""
    channel_id = int(callback.data.split("_")[-1])
    channel = await db.get_channel_by_id(channel_id)
    
    await state.update_data(channel_id=channel_id)
    
    await callback.message.edit_text(
        f"📝 <b>Создание поста для канала:</b>\n"
        f"📢 {channel['channel_title'] or channel['channel_username']}\n\n"
        "Введите текст поста (поддерживается HTML форматирование):",
        parse_mode="HTML"
    )
    await state.set_state(CreatePostStates.enter_text)
    await callback.answer()


@router.message(CreatePostStates.select_channel, F.forward_from_chat)
async def add_channel_from_forward(message: Message, state: FSMContext, bot: Bot):
    """Добавление канала через пересланное сообщение"""
    chat = message.forward_from_chat
    
    if chat.type not in ['channel']:
        await message.answer("⚠️ Это не канал. Перешлите сообщение из канала.")
        return
    
    # Проверяем права бота в канале
    try:
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                "⚠️ Бот не является администратором этого канала.\n"
                "Добавьте бота в канал как администратора с правами на публикацию сообщений."
            )
            return
        
        if not getattr(bot_member, 'can_post_messages', False):
            await message.answer(
                "⚠️ У бота нет прав на публикацию сообщений в этом канале.\n"
                "Дайте боту права на публикацию сообщений."
            )
            return
    except Exception as e:
        logger.error(f"Check bot rights error: {e}")
        await message.answer(f"⚠️ Не удалось проверить права бота: {e}")
        return
    
    # Проверяем права пользователя
    try:
        user_member = await bot.get_chat_member(chat.id, message.from_user.id)
        if user_member.status not in ['creator', 'administrator']:
            await message.answer("⚠️ Вы не являетесь администратором этого канала.")
            return
    except Exception as e:
        logger.error(f"Check user rights error: {e}")
        await message.answer(f"⚠️ Не удалось проверить ваши права: {e}")
        return
    
    # Добавляем канал
    await db.add_channel(
        channel_id=chat.id,
        username=chat.username,
        title=chat.title,
        added_by=message.from_user.id
    )
    
    await state.update_data(channel_id=chat.id)
    
    await message.answer(
        f"✅ <b>Канал добавлен!</b>\n"
        f"📢 {chat.title}\n\n"
        "Теперь введите текст поста (поддерживается HTML форматирование):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePostStates.enter_text)


@router.message(CreatePostStates.enter_text, F.text)
async def post_text_received(message: Message, state: FSMContext):
    """Получен текст поста"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание поста отменено", reply_markup=get_main_menu())
        return
    
    await state.update_data(post_text=message.text)
    data = await state.get_data()
    
    # Показываем конструктор
    has_media = data.get('media_file_id') is not None
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Текст добавлен!</b>\n\n"
        "Теперь вы можете добавить дополнительные элементы или опубликовать пост:",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=True,
            has_media=has_media,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.enter_text, F.photo)
async def post_photo_as_text(message: Message, state: FSMContext):
    """Получено фото вместо текста"""
    await state.update_data(
        media_type='photo',
        media_file_id=message.photo[-1].file_id,
        post_text=message.caption or ''
    )
    
    data = await state.get_data()
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Фото добавлено!</b>\n\n"
        "Теперь вы можете добавить дополнительные элементы или опубликовать пост:",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=bool(message.caption),
            has_media=True,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.enter_text, F.video)
async def post_video_as_text(message: Message, state: FSMContext):
    """Получено видео вместо текста"""
    await state.update_data(
        media_type='video',
        media_file_id=message.video.file_id,
        post_text=message.caption or ''
    )
    
    data = await state.get_data()
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Видео добавлено!</b>\n\n"
        "Теперь вы можете добавить дополнительные элементы или опубликовать пост:",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=bool(message.caption),
            has_media=True,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.enter_text, F.document)
async def post_document_as_text(message: Message, state: FSMContext):
    """Получен документ вместо текста"""
    await state.update_data(
        media_type='document',
        media_file_id=message.document.file_id,
        post_text=message.caption or ''
    )
    
    data = await state.get_data()
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Документ добавлен!</b>\n\n"
        "Теперь вы можете добавить дополнительные элементы или опубликовать пост:",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=bool(message.caption),
            has_media=True,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


# ============ Конструктор поста ============

@router.callback_query(CreatePostStates.constructor, F.data == "edit_text")
async def edit_text(callback: CallbackQuery, state: FSMContext):
    """Редактирование текста"""
    await callback.message.edit_text(
        "✏️ <b>Введите новый текст поста:</b>",
        parse_mode="HTML"
    )
    await state.set_state(CreatePostStates.enter_text)
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "add_media")
@router.callback_query(CreatePostStates.constructor, F.data == "edit_media")
async def add_media(callback: CallbackQuery, state: FSMContext):
    """Добавление/изменение медиафайла"""
    await callback.message.edit_text(
        "🖼 <b>Отправьте медиафайл:</b>\n\n"
        "• 📷 Фото (до 10 MB)\n"
        "• 🎥 Видео (до 50 MB)\n"
        "• 📄 Документ",
        parse_mode="HTML",
        reply_markup=get_back_inline_keyboard("back_to_constructor")
    )
    await state.set_state(CreatePostStates.add_media)
    await callback.answer()


@router.message(CreatePostStates.add_media, F.photo)
async def media_photo_received(message: Message, state: FSMContext):
    """Получено фото"""
    await state.update_data(
        media_type='photo',
        media_file_id=message.photo[-1].file_id
    )
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Фото добавлено!</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=True,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.add_media, F.video)
async def media_video_received(message: Message, state: FSMContext):
    """Получено видео"""
    await state.update_data(
        media_type='video',
        media_file_id=message.video.file_id
    )
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Видео добавлено!</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=True,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.message(CreatePostStates.add_media, F.document)
async def media_document_received(message: Message, state: FSMContext):
    """Получен документ"""
    await state.update_data(
        media_type='document',
        media_file_id=message.document.file_id
    )
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_buttons = data.get('buttons_text') is not None
    
    await message.answer(
        "✅ <b>Документ добавлен!</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=True,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.callback_query(CreatePostStates.constructor, F.data == "remove_media")
async def remove_media(callback: CallbackQuery, state: FSMContext):
    """Удаление медиафайла"""
    await state.update_data(media_type=None, media_file_id=None)
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_buttons = data.get('buttons_text') is not None
    
    await callback.message.edit_text(
        "🗑 <b>Медиафайл удален</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=False,
            has_buttons=has_buttons
        )
    )
    await callback.answer("Медиафайл удален")


@router.callback_query(CreatePostStates.constructor, F.data == "add_buttons")
@router.callback_query(CreatePostStates.constructor, F.data == "edit_buttons")
async def add_buttons(callback: CallbackQuery, state: FSMContext):
    """Добавление URL-кнопок"""
    await callback.message.edit_text(
        "🔗 <b>Отправьте список URL-кнопок в одном сообщении.</b>\n\n"
        "Пожалуйста, следуйте этому формату:\n\n"
        "<code>Кнопка 1 - http://example1.com\n"
        "Кнопка 2 - http://example2.com</code>\n\n"
        "Используйте разделитель <code>|</code>, чтобы добавить до трех кнопок в один ряд:\n\n"
        "<code>Кнопка 1 - http://example1.com | Кнопка 2 - http://example2.com</code>",
        parse_mode="HTML",
        reply_markup=get_back_inline_keyboard("back_to_constructor")
    )
    await state.set_state(CreatePostStates.add_buttons)
    await callback.answer()


@router.message(CreatePostStates.add_buttons, F.text)
async def buttons_received(message: Message, state: FSMContext):
    """Получены кнопки"""
    keyboard = parse_url_buttons(message.text)
    
    if not keyboard:
        await message.answer(
            "⚠️ <b>Не удалось распознать кнопки.</b>\n\n"
            "Проверьте формат:\n"
            "<code>Кнопка - http://url</code>",
            parse_mode="HTML",
            reply_markup=get_back_inline_keyboard("back_to_constructor")
        )
        return
    
    await state.update_data(buttons_text=message.text)
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_media = data.get('media_file_id') is not None
    
    await message.answer(
        "✅ <b>Кнопки добавлены!</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=has_media,
            has_buttons=True
        )
    )
    await state.set_state(CreatePostStates.constructor)


@router.callback_query(CreatePostStates.constructor, F.data == "remove_buttons")
async def remove_buttons(callback: CallbackQuery, state: FSMContext):
    """Удаление кнопок"""
    await state.update_data(buttons_text=None)
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_media = data.get('media_file_id') is not None
    
    await callback.message.edit_text(
        "🗑 <b>Кнопки удалены</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=has_media,
            has_buttons=False
        )
    )
    await callback.answer("Кнопки удалены")


@router.callback_query(F.data == "back_to_constructor")
async def back_to_constructor(callback: CallbackQuery, state: FSMContext):
    """Возврат в конструктор"""
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_media = data.get('media_file_id') is not None
    has_buttons = data.get('buttons_text') is not None
    
    await callback.message.edit_text(
        "📝 <b>Конструктор поста</b>\n\n"
        "Добавьте элементы или продолжите:",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=has_media,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)
    await callback.answer()


# ============ Предпросмотр и публикация ============

@router.callback_query(CreatePostStates.constructor, F.data == "preview")
async def preview_post(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Предпросмотр поста"""
    data = await state.get_data()
    
    if not data.get('post_text') and not data.get('media_file_id'):
        await callback.answer("⚠️ Добавьте текст или медиафайл", show_alert=True)
        return
    
    await callback.message.delete()
    success = await send_post_preview(callback.message, data, bot)
    
    if success:
        has_text = bool(data.get('post_text'))
        has_media = data.get('media_file_id') is not None
        has_buttons = data.get('buttons_text') is not None
        
        await callback.message.answer(
            "⬆️ <b>Предпросмотр выше</b>\n\n"
            "Продолжите редактирование или опубликуйте:",
            parse_mode="HTML",
            reply_markup=get_post_constructor_keyboard(
                has_text=has_text,
                has_media=has_media,
                has_buttons=has_buttons
            )
        )
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "next_step")
async def next_step(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход к публикации"""
    data = await state.get_data()
    
    if not data.get('post_text') and not data.get('media_file_id'):
        await callback.answer("⚠️ Добавьте текст или медиафайл", show_alert=True)
        return
    
    await callback.message.delete()
    success = await send_post_preview(callback.message, data, bot)
    
    if success:
        await callback.message.answer(
            "📤 <b>Готово к публикации!</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_publish_keyboard()
        )
        await state.set_state(CreatePostStates.publish_menu)
    await callback.answer()


@router.callback_query(CreatePostStates.constructor, F.data == "cancel_post")
@router.callback_query(CreatePostStates.publish_menu, F.data == "cancel_post")
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    """Отмена создания поста"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "❌ Создание поста отменено",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "back_to_edit")
async def back_to_edit(callback: CallbackQuery, state: FSMContext):
    """Вернуться к редактированию"""
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_media = data.get('media_file_id') is not None
    has_buttons = data.get('buttons_text') is not None
    
    await callback.message.edit_text(
        "📝 <b>Конструктор поста</b>",
        parse_mode="HTML",
        reply_markup=get_post_constructor_keyboard(
            has_text=has_text,
            has_media=has_media,
            has_buttons=has_buttons
        )
    )
    await state.set_state(CreatePostStates.constructor)
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "publish_now")
async def publish_now(callback: CallbackQuery, state: FSMContext):
    """Мгновенная публикация"""
    await callback.message.edit_text(
        "❓ <b>Вы уверены, что хотите опубликовать пост?</b>",
        parse_mode="HTML",
        reply_markup=get_confirm_publish_keyboard()
    )
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "back_to_publish_menu")
async def back_to_publish_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню публикации"""
    await callback.message.edit_text(
        "📤 <b>Готово к публикации!</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_publish_keyboard()
    )
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data == "confirm_publish")
async def confirm_publish(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение публикации"""
    data = await state.get_data()
    channel_id = data.get('channel_id')
    
    success, result = await publish_post(bot, channel_id, data, callback.from_user.id)
    
    if success:
        channel = await db.get_channel_by_id(channel_id)
        channel_username = channel['channel_username'] if channel else None
        
        await state.clear()
        await callback.message.edit_text(
            "✅ <b>Пост успешно опубликован!</b>",
            parse_mode="HTML",
            reply_markup=get_view_post_keyboard(channel_username, result.message_id)
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации:</b>\n{result}",
            parse_mode="HTML",
            reply_markup=get_back_inline_keyboard("back_to_publish_menu")
        )
    await callback.answer()


# ============ Отложенная публикация ============

@router.callback_query(CreatePostStates.publish_menu, F.data == "schedule_post")
async def schedule_post_menu(callback: CallbackQuery, state: FSMContext):
    """Меню отложенной публикации"""
    await callback.message.edit_text(
        "⏰ <b>Выберите время публикации:</b>",
        parse_mode="HTML",
        reply_markup=get_schedule_keyboard()
    )
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data.startswith("schedule_"))
async def schedule_preset(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Отложенная публикация с предустановленным временем"""
    preset = callback.data.replace("schedule_", "")
    now = datetime.now()
    
    if preset == "1h":
        scheduled_time = now + timedelta(hours=1)
    elif preset == "3h":
        scheduled_time = now + timedelta(hours=3)
    elif preset == "6h":
        scheduled_time = now + timedelta(hours=6)
    elif preset == "tomorrow":
        tomorrow = now + timedelta(days=1)
        scheduled_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    elif preset == "custom":
        await callback.message.edit_text(
            "📅 <b>Введите время публикации:</b>\n\n"
            "Формат: <code>ЧЧ ММ ДД ММ</code>\n"
            "Пример: <code>14 00 04 12</code> — 4 декабря в 14:00",
            parse_mode="HTML",
            reply_markup=get_back_inline_keyboard("back_to_publish_menu")
        )
        await state.set_state(CreatePostStates.schedule_custom)
        await callback.answer()
        return
    else:
        await callback.answer("⚠️ Неизвестный вариант")
        return
    
    await save_scheduled_post(callback, state, scheduled_time)


@router.message(CreatePostStates.schedule_custom, F.text)
async def schedule_custom_time(message: Message, state: FSMContext):
    """Пользовательское время публикации"""
    try:
        parts = message.text.strip().split()
        if len(parts) != 4:
            raise ValueError("Неверный формат")
        
        hour, minute, day, month = map(int, parts)
        year = datetime.now().year
        
        # Если месяц уже прошел - берем следующий год
        if month < datetime.now().month:
            year += 1
        
        scheduled_time = datetime(year, month, day, hour, minute)
        
        if scheduled_time <= datetime.now():
            await message.answer(
                "⚠️ <b>Время должно быть в будущем</b>\n\n"
                "Попробуйте снова:",
                parse_mode="HTML"
            )
            return
        
        data = await state.get_data()
        channel_id = data.get('channel_id')
        
        post_id = await db.add_scheduled_post(
            channel_id=channel_id,
            user_id=message.from_user.id,
            text=data.get('post_text', ''),
            media_type=data.get('media_type'),
            media_file_id=data.get('media_file_id'),
            buttons=data.get('buttons_text'),
            scheduled_time=scheduled_time,
            delete_after=data.get('delete_after')
        )
        
        await state.clear()
        
        time_str = scheduled_time.strftime("%d %B в %H:%M")
        await message.answer(
            f"⏰ <b>Отложенный пост создан!</b>\n\n"
            f"📅 Будет опубликован: {time_str}",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    
    except ValueError:
        await message.answer(
            "⚠️ <b>Неверный формат!</b>\n\n"
            "Используйте: <code>ЧЧ ММ ДД ММ</code>\n"
            "Пример: <code>14 00 04 12</code>",
            parse_mode="HTML"
        )


async def save_scheduled_post(callback: CallbackQuery, state: FSMContext, scheduled_time: datetime):
    """Сохранение отложенного поста"""
    data = await state.get_data()
    channel_id = data.get('channel_id')
    
    post_id = await db.add_scheduled_post(
        channel_id=channel_id,
        user_id=callback.from_user.id,
        text=data.get('post_text', ''),
        media_type=data.get('media_type'),
        media_file_id=data.get('media_file_id'),
        buttons=data.get('buttons_text'),
        scheduled_time=scheduled_time,
        delete_after=data.get('delete_after')
    )
    
    await state.clear()
    
    time_str = scheduled_time.strftime("%d %B в %H:%M")
    await callback.message.edit_text(
        f"⏰ <b>Отложенный пост создан!</b>\n\n"
        f"📅 Будет опубликован: {time_str}",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_menu()
    )
    await callback.answer()


# ============ Таймер удаления ============

@router.callback_query(CreatePostStates.publish_menu, F.data == "set_delete_timer")
async def set_delete_timer(callback: CallbackQuery, state: FSMContext):
    """Меню таймера удаления"""
    await callback.message.edit_text(
        "⏱ <b>Установить таймер удаления:</b>\n\n"
        "Пост будет автоматически удален через указанное время после публикации.",
        parse_mode="HTML",
        reply_markup=get_delete_timer_keyboard()
    )
    await callback.answer()


@router.callback_query(CreatePostStates.publish_menu, F.data.startswith("delete_"))
async def delete_timer_preset(callback: CallbackQuery, state: FSMContext):
    """Установка таймера удаления"""
    preset = callback.data.replace("delete_", "")
    
    if preset == "1h":
        delete_after = 3600
    elif preset == "6h":
        delete_after = 21600
    elif preset == "12h":
        delete_after = 43200
    elif preset == "24h":
        delete_after = 86400
    elif preset == "custom":
        await callback.message.edit_text(
            "⏱ <b>Введите время в минутах:</b>",
            parse_mode="HTML",
            reply_markup=get_back_inline_keyboard("back_to_publish_menu")
        )
        await state.set_state(CreatePostStates.delete_timer_custom)
        await callback.answer()
        return
    else:
        await callback.answer("⚠️ Неизвестный вариант")
        return
    
    await state.update_data(delete_after=delete_after)
    
    hours = delete_after // 3600
    await callback.message.edit_text(
        f"✅ <b>Таймер установлен: {hours} ч.</b>\n\n"
        "Пост будет удален через это время после публикации.\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_publish_keyboard()
    )
    await callback.answer()


@router.message(CreatePostStates.delete_timer_custom, F.text)
async def delete_timer_custom(message: Message, state: FSMContext):
    """Пользовательский таймер удаления"""
    try:
        minutes = int(message.text.strip())
        if minutes <= 0:
            raise ValueError()
        
        delete_after = minutes * 60
        await state.update_data(delete_after=delete_after)
        
        await message.answer(
            f"✅ <b>Таймер установлен: {minutes} мин.</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_publish_keyboard()
        )
        await state.set_state(CreatePostStates.publish_menu)
    
    except ValueError:
        await message.answer(
            "⚠️ <b>Введите целое положительное число минут</b>",
            parse_mode="HTML"
        )


# ============ Добавление канала ============

@router.callback_query(F.data == "add_channel")
@router.message(Command("addchannel"))
async def add_channel_cmd(update, state: FSMContext):
    """Добавление нового канала"""
    text = (
        "📢 <b>Добавление канала</b>\n\n"
        "1. Добавьте бота в канал как администратора\n"
        "2. Дайте боту права на публикацию сообщений\n"
        "3. Перешлите мне любое сообщение из канала"
    )
    
    if isinstance(update, CallbackQuery):
        await update.message.edit_text(text, parse_mode="HTML")
        await update.answer()
    else:
        await update.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    
    await state.set_state(CreatePostStates.select_channel)
