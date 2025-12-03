from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards import get_main_menu, get_cancel_keyboard, get_channels_keyboard
import database as db

router = Router()


class PollStates(StatesGroup):
    """Состояния для создания опроса"""
    select_channel = State()
    enter_question = State()
    enter_options = State()
    settings = State()


@router.message(F.text == "📊 Опрос")
async def create_poll_start(message: Message, state: FSMContext):
    """Начало создания опроса"""
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
            "📊 <b>Создание опроса</b>\n\n"
            "Введите <b>вопрос</b> для опроса:",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(PollStates.enter_question)
    else:
        buttons = []
        for ch in channels:
            title = ch['channel_title'] or ch['channel_username']
            buttons.append([
                InlineKeyboardButton(text=f"📢 {title}", callback_data=f"poll_channel_{ch['channel_id']}")
            ])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
        
        await message.answer(
            "📊 <b>Создание опроса</b>\n\n"
            "Выберите канал:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await state.set_state(PollStates.select_channel)


@router.callback_query(PollStates.select_channel, F.data.startswith("poll_channel_"))
async def poll_channel_selected(callback: CallbackQuery, state: FSMContext):
    """Канал выбран для опроса"""
    channel_id = int(callback.data.split("_")[-1])
    await state.update_data(channel_id=channel_id)
    
    await callback.message.edit_text(
        "📊 <b>Создание опроса</b>\n\n"
        "Введите <b>вопрос</b> для опроса:",
        parse_mode="HTML"
    )
    await state.set_state(PollStates.enter_question)
    await callback.answer()


@router.message(PollStates.enter_question, F.text)
async def poll_question_received(message: Message, state: FSMContext):
    """Получен вопрос опроса"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание опроса отменено", reply_markup=get_main_menu())
        return
    
    await state.update_data(question=message.text)
    
    await message.answer(
        "📊 <b>Отлично!</b>\n\n"
        "Теперь введите <b>варианты ответов</b>, каждый с новой строки.\n\n"
        "Пример:\n"
        "<code>Вариант 1\n"
        "Вариант 2\n"
        "Вариант 3</code>\n\n"
        "Минимум 2, максимум 10 вариантов.",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(PollStates.enter_options)


@router.message(PollStates.enter_options, F.text)
async def poll_options_received(message: Message, state: FSMContext):
    """Получены варианты ответов"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание опроса отменено", reply_markup=get_main_menu())
        return
    
    options = [opt.strip() for opt in message.text.split('\n') if opt.strip()]
    
    if len(options) < 2:
        await message.answer(
            "⚠️ <b>Минимум 2 варианта ответа</b>\n\n"
            "Введите варианты, каждый с новой строки:",
            parse_mode="HTML"
        )
        return
    
    if len(options) > 10:
        await message.answer(
            "⚠️ <b>Максимум 10 вариантов ответа</b>\n\n"
            "Сократите список и отправьте снова:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(options=options, is_anonymous=True, allows_multiple=False)
    data = await state.get_data()
    
    # Показываем настройки опроса
    await message.answer(
        f"📊 <b>Предпросмотр опроса</b>\n\n"
        f"❓ <b>Вопрос:</b> {data['question']}\n\n"
        f"📝 <b>Варианты:</b>\n" + "\n".join([f"• {opt}" for opt in options]) + "\n\n"
        "Настройте опрос:",
        parse_mode="HTML",
        reply_markup=get_poll_settings_keyboard(
            is_anonymous=True,
            allows_multiple=False
        )
    )
    await state.set_state(PollStates.settings)


def get_poll_settings_keyboard(is_anonymous: bool, allows_multiple: bool):
    """Клавиатура настроек опроса"""
    anon_text = "👤 Анонимный: ✅" if is_anonymous else "👤 Анонимный: ❌"
    multi_text = "☑️ Несколько ответов: ✅" if allows_multiple else "☑️ Несколько ответов: ❌"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=anon_text, callback_data="toggle_anonymous")],
        [InlineKeyboardButton(text=multi_text, callback_data="toggle_multiple")],
        [InlineKeyboardButton(text="📤 Опубликовать опрос", callback_data="publish_poll")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_poll")]
    ])


@router.callback_query(PollStates.settings, F.data == "toggle_anonymous")
async def toggle_anonymous(callback: CallbackQuery, state: FSMContext):
    """Переключение анонимности"""
    data = await state.get_data()
    is_anonymous = not data.get('is_anonymous', True)
    await state.update_data(is_anonymous=is_anonymous)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_poll_settings_keyboard(
            is_anonymous=is_anonymous,
            allows_multiple=data.get('allows_multiple', False)
        )
    )
    await callback.answer()


@router.callback_query(PollStates.settings, F.data == "toggle_multiple")
async def toggle_multiple(callback: CallbackQuery, state: FSMContext):
    """Переключение множественного выбора"""
    data = await state.get_data()
    allows_multiple = not data.get('allows_multiple', False)
    await state.update_data(allows_multiple=allows_multiple)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_poll_settings_keyboard(
            is_anonymous=data.get('is_anonymous', True),
            allows_multiple=allows_multiple
        )
    )
    await callback.answer()


@router.callback_query(PollStates.settings, F.data == "publish_poll")
async def publish_poll(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Публикация опроса"""
    data = await state.get_data()
    channel_id = data.get('channel_id')
    
    try:
        await bot.send_poll(
            chat_id=channel_id,
            question=data['question'],
            options=data['options'],
            is_anonymous=data.get('is_anonymous', True),
            allows_multiple_answers=data.get('allows_multiple', False)
        )
        
        await state.clear()
        
        channel = await db.get_channel_by_id(channel_id)
        username = channel['channel_username'] if channel else None
        
        if username:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Открыть канал", url=f"https://t.me/{username.lstrip('@')}")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        
        await callback.message.edit_text(
            "✅ <b>Опрос опубликован!</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации:</b>\n{e}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
    
    await callback.answer()


@router.callback_query(PollStates.settings, F.data == "cancel_poll")
async def cancel_poll(callback: CallbackQuery, state: FSMContext):
    """Отмена создания опроса"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "❌ Создание опроса отменено",
        reply_markup=get_main_menu()
    )
    await callback.answer()
