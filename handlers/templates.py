from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import get_main_menu, get_cancel_keyboard, parse_url_buttons
import database as db

router = Router()


class TemplateStates(StatesGroup):
    """Состояния для работы с шаблонами"""
    enter_name = State()
    viewing = State()


@router.message(F.text == "📋 Шаблоны")
async def show_templates(message: Message, state: FSMContext):
    """Показать шаблоны"""
    await state.clear()
    
    templates = await db.get_user_templates(message.from_user.id)
    
    buttons = [
        [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="create_template")]
    ]
    
    if templates:
        for tpl in templates:
            name = tpl['name'][:30]
            buttons.append([
                InlineKeyboardButton(text=f"📋 {name}", callback_data=f"use_template_{tpl['id']}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_template_{tpl['id']}")
            ])
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    
    text = f"📋 <b>Шаблоны постов ({len(templates)})</b>\n\n"
    if templates:
        text += "Выберите шаблон для использования или создайте новый:"
    else:
        text += "У вас пока нет шаблонов.\nСоздайте первый шаблон!"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data == "create_template")
async def create_template_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания шаблона"""
    await callback.message.edit_text(
        "📋 <b>Создание шаблона</b>\n\n"
        "Отправьте пост, который хотите сохранить как шаблон.\n\n"
        "Можно отправить:\n"
        "• Текст\n"
        "• Фото с подписью\n"
        "• Видео с подписью",
        parse_mode="HTML"
    )
    await state.set_state(TemplateStates.enter_name)
    await state.update_data(waiting_content=True)
    await callback.answer()


@router.message(TemplateStates.enter_name, F.text)
async def template_text_received(message: Message, state: FSMContext):
    """Получен текст для шаблона"""
    data = await state.get_data()
    
    if data.get('waiting_content'):
        # Это контент шаблона
        await state.update_data(
            template_text=message.text,
            media_type=None,
            media_file_id=None,
            waiting_content=False
        )
        await message.answer(
            "✅ Контент получен!\n\n"
            "Теперь введите <b>название</b> для шаблона:",
            parse_mode="HTML"
        )
    else:
        # Это название шаблона
        template_data = await state.get_data()
        
        await db.add_template(
            user_id=message.from_user.id,
            name=message.text,
            text=template_data.get('template_text', ''),
            media_type=template_data.get('media_type'),
            media_file_id=template_data.get('media_file_id'),
            buttons=template_data.get('buttons_text')
        )
        
        await state.clear()
        await message.answer(
            f"✅ <b>Шаблон «{message.text}» сохранён!</b>",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )


@router.message(TemplateStates.enter_name, F.photo)
async def template_photo_received(message: Message, state: FSMContext):
    """Получено фото для шаблона"""
    await state.update_data(
        template_text=message.caption or '',
        media_type='photo',
        media_file_id=message.photo[-1].file_id,
        waiting_content=False
    )
    await message.answer(
        "✅ Фото получено!\n\n"
        "Теперь введите <b>название</b> для шаблона:",
        parse_mode="HTML"
    )


@router.message(TemplateStates.enter_name, F.video)
async def template_video_received(message: Message, state: FSMContext):
    """Получено видео для шаблона"""
    await state.update_data(
        template_text=message.caption or '',
        media_type='video',
        media_file_id=message.video.file_id,
        waiting_content=False
    )
    await message.answer(
        "✅ Видео получено!\n\n"
        "Теперь введите <b>название</b> для шаблона:",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("use_template_"))
async def use_template(callback: CallbackQuery, state: FSMContext):
    """Использовать шаблон"""
    template_id = int(callback.data.split("_")[-1])
    template = await db.get_template(template_id)
    
    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    
    # Получаем каналы
    channels = await db.get_channels(callback.from_user.id)
    
    if not channels:
        await callback.message.edit_text(
            "❌ У вас нет подключенных каналов.\n"
            "Сначала добавьте канал.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Сохраняем данные шаблона в FSM
    await state.update_data(
        post_text=template['text'],
        media_type=template['media_type'],
        media_file_id=template['media_file_id'],
        buttons_text=template['buttons'],
        from_template=True
    )
    
    if len(channels) == 1:
        await state.update_data(channel_id=channels[0]['channel_id'])
        
        # Показываем превью и опции
        text = f"📋 <b>Шаблон «{template['name']}» загружен!</b>\n\n"
        if template['text']:
            text += f"📝 Текст: <i>{template['text'][:100]}...</i>\n"
        if template['media_type']:
            text += f"📎 Медиа: {template['media_type']}\n"
        
        await callback.message.edit_text(
            text + "\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📤 Опубликовать", callback_data="publish_from_template")],
                [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_from_template")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_templates")]
            ])
        )
    else:
        # Выбор канала
        buttons = []
        for ch in channels:
            title = ch['channel_title'] or ch['channel_username']
            buttons.append([
                InlineKeyboardButton(text=f"📢 {title}", callback_data=f"template_channel_{ch['channel_id']}")
            ])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_templates")])
        
        await callback.message.edit_text(
            "📢 <b>Выберите канал для публикации:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("template_channel_"))
async def template_channel_selected(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Канал выбран для шаблона"""
    channel_id = int(callback.data.split("_")[-1])
    await state.update_data(channel_id=channel_id)
    
    data = await state.get_data()
    
    await callback.message.edit_text(
        "📋 <b>Шаблон загружен!</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Опубликовать", callback_data="publish_from_template")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_from_template")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_templates")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "publish_from_template")
async def publish_from_template(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Публикация из шаблона"""
    data = await state.get_data()
    channel_id = data.get('channel_id')
    
    text = data.get('post_text', '')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons_text = data.get('buttons_text')
    
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
        else:
            msg = await bot.send_message(
                chat_id=channel_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
        
        await db.add_post_stats(channel_id, msg.message_id)
        await state.clear()
        
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
        
        await callback.message.edit_text(
            "✅ <b>Пост из шаблона опубликован!</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации:</b>\n{e}",
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data == "edit_from_template")
async def edit_from_template(callback: CallbackQuery, state: FSMContext):
    """Редактировать шаблон перед публикацией"""
    from handlers.create_post import CreatePostStates, get_post_constructor_keyboard
    
    data = await state.get_data()
    has_text = bool(data.get('post_text'))
    has_media = data.get('media_file_id') is not None
    has_buttons = data.get('buttons_text') is not None
    
    await callback.message.edit_text(
        "📝 <b>Редактирование поста из шаблона</b>\n\n"
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


@router.callback_query(F.data.startswith("delete_template_"))
async def delete_template(callback: CallbackQuery):
    """Удалить шаблон"""
    template_id = int(callback.data.split("_")[-1])
    
    await callback.message.edit_text(
        "❓ <b>Удалить этот шаблон?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_del_tpl_{template_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="back_to_templates")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_tpl_"))
async def confirm_delete_template(callback: CallbackQuery):
    """Подтверждение удаления шаблона"""
    template_id = int(callback.data.split("_")[-1])
    await db.delete_template(template_id)
    
    await callback.answer("Шаблон удалён!")
    
    # Показываем обновлённый список
    templates = await db.get_user_templates(callback.from_user.id)
    
    buttons = [
        [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="create_template")]
    ]
    
    for tpl in templates:
        name = tpl['name'][:30]
        buttons.append([
            InlineKeyboardButton(text=f"📋 {name}", callback_data=f"use_template_{tpl['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_template_{tpl['id']}")
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    
    await callback.message.edit_text(
        f"📋 <b>Шаблоны ({len(templates)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data == "back_to_templates")
async def back_to_templates(callback: CallbackQuery, state: FSMContext):
    """Вернуться к списку шаблонов"""
    await state.clear()
    
    templates = await db.get_user_templates(callback.from_user.id)
    
    buttons = [
        [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="create_template")]
    ]
    
    for tpl in templates:
        name = tpl['name'][:30]
        buttons.append([
            InlineKeyboardButton(text=f"📋 {name}", callback_data=f"use_template_{tpl['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_template_{tpl['id']}")
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    
    await callback.message.edit_text(
        f"📋 <b>Шаблоны ({len(templates)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()
