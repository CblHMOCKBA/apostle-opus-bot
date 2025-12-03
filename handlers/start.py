from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from keyboards import get_main_menu
import database as db

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    # Получаем или создаем настройки пользователя
    await db.get_user_settings(message.from_user.id)
    
    text = """👋 <b>Добро пожаловать в ApostleOpus Posting Bot!</b>

Здесь вы можете создавать посты, просматривать статистику и выполнять другие задачи.

📢 <i>Для начала работы добавьте бота в канал как администратора с правами на публикацию сообщений.</i>

💡 <b>Подсказка:</b> Используйте HTML для форматирования:
<code>&lt;b&gt;жирный&lt;/b&gt;</code> → <b>жирный</b>
<code>&lt;i&gt;курсив&lt;/i&gt;</code> → <i>курсив</i>"""
    
    await message.answer(text, reply_markup=get_main_menu(), parse_mode="HTML")


@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    """Обработчик кнопки отмены"""
    await state.clear()
    await message.answer(
        "❌ Действие отменено",
        reply_markup=get_main_menu()
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по боту"""
    text = """📖 <b>Справка по боту</b>

🔹 <b>Создание поста:</b>
1. Нажмите "Создать пост"
2. Введите текст
3. Добавьте кнопки и медиа
4. Опубликуйте или отложите

🔹 <b>Форматирование текста:</b>
Пишите теги прямо в тексте поста:

<code>&lt;b&gt;жирный&lt;/b&gt;</code> → <b>жирный</b>
<code>&lt;i&gt;курсив&lt;/i&gt;</code> → <i>курсив</i>
<code>&lt;u&gt;подчёркнутый&lt;/u&gt;</code> → <u>подчёркнутый</u>
<code>&lt;s&gt;зачёркнутый&lt;/s&gt;</code> → <s>зачёркнутый</s>
<code>&lt;code&gt;код&lt;/code&gt;</code> → <code>код</code>
<code>&lt;a href="url"&gt;ссылка&lt;/a&gt;</code> → ссылка

🔹 <b>URL-кнопки:</b>
Формат: <code>Название - http://ссылка</code>
Разделитель <code>|</code> для кнопок в ряд

🔹 <b>Команды:</b>
/start - Главное меню
/newpost - Создать пост
/scheduled - Отложенные посты
/settings - Настройки
/help - Эта справка

❓ Остались вопросы? Напишите разработчику."""
    
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🚀 Рекламировать Ваш канал")
async def advertise_channel(message: Message):
    """Заглушка для рекламы канала"""
    await message.answer(
        "🚀 <b>Рекламировать Ваш канал</b>\n\n"
        "Эта функция находится в разработке.\n"
        "Скоро здесь появится возможность продвижения вашего канала!",
        parse_mode="HTML"
    )


@router.message(Command("format"))
async def cmd_format(message: Message):
    """Справка по форматированию"""
    text = """✨ <b>Форматирование текста</b>

Пишите HTML теги прямо в тексте поста:

<b>Жирный:</b>
<code>&lt;b&gt;текст&lt;/b&gt;</code>
Результат: <b>текст</b>

<b>Курсив:</b>
<code>&lt;i&gt;текст&lt;/i&gt;</code>
Результат: <i>текст</i>

<b>Подчёркнутый:</b>
<code>&lt;u&gt;текст&lt;/u&gt;</code>
Результат: <u>текст</u>

<b>Зачёркнутый:</b>
<code>&lt;s&gt;текст&lt;/s&gt;</code>
Результат: <s>текст</s>

<b>Моноширинный:</b>
<code>&lt;code&gt;текст&lt;/code&gt;</code>
Результат: <code>текст</code>

<b>Ссылка:</b>
<code>&lt;a href="https://google.com"&gt;Google&lt;/a&gt;</code>
Результат: <a href="https://google.com">Google</a>

<b>Комбинация:</b>
<code>&lt;b&gt;&lt;i&gt;жирный курсив&lt;/i&gt;&lt;/b&gt;</code>
Результат: <b><i>жирный курсив</i></b>

💡 Копируйте примеры и меняйте текст!"""
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
