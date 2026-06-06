import os
import datetime
import pytz
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

from voice_handler import download_voice, transcribe_voice
from calendar_handler import parse_event, add_event_to_calendar, get_events_for_period, delete_event_by_id, TIMEZONE_STR, utc_to_local
from scheduler import daily_report, check_reminders

# Загружаем переменные окружения из файла .env
load_dotenv("/my_planner_bot/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Хранилище для временных данных пользователя (например, список событий для удаления)
user_data = {}
CHAT_ID = None

# Часовой пояс Перми
PERM_TZ = pytz.timezone("Asia/Yekaterinburg")


def get_main_keyboard():
    """Создаёт главную клавиатуру с тремя кнопками: Удалить, 7 дней, Календарь"""
    keyboard = [
        [
            InlineKeyboardButton("Удалить", callback_data="delete"),
            InlineKeyboardButton("7 дней", callback_data="week"),
            InlineKeyboardButton("Календарь", url="https://calendar.google.com/calendar/u/0/r/week")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard():
     """Создаёт клавиатуру только с одной кнопкой "Назад" для возврата в главное меню"""
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back")]]
    return InlineKeyboardMarkup(keyboard)


def get_events_keyboard(events, action="delete"):
    """
    Создаёт клавиатуру со списком событий для выбора.
    Каждая кнопка содержит название события и время, callback_data содержит action и ID события.
    В конце добавляется кнопка "Назад".
    """
    keyboard = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        if "T" in start:
            # Парсим UTC время и конвертируем в Пермь
            if start.endswith('Z'):
                start = start.replace('Z', '+00:00')
            utc_time = datetime.datetime.fromisoformat(start)
            perm_time = utc_to_local(utc_time)
            date_str = perm_time.strftime("%d.%m.%Y")
            time_str = perm_time.strftime("%H:%M")
            display = f"{event['summary']} ({date_str} {time_str})"
        else:
            display = f"{event['summary']} ({start})"
        if len(display) > 40:
            display = display[:37] + "..."
        keyboard.append([InlineKeyboardButton(display, callback_data=f"{action}_{event['id']}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start.
    Сохраняет chat_id пользователя, настраивает планировщик и отправляет приветственное сообщение с клавиатурой.
    """
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    context.application.chat_id = CHAT_ID
    await update.message.reply_text(
        "👋 Привет! Я твой календарь-бот.\n\n"
        "📝 Какие планы? Просто напиши или наговори сообщение.\n\n"
        "Например: Встреча завтра в 9:30.\n\n"
        "🗑 Удалить событие\n"
        "📅 Показать план на 7 дней\n"
        "📆 Открыть календарь",
        reply_markup=get_main_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатий на инлайн-кнопки.
    Определяет, какая кнопка нажата (delete, week, back, delete_*, confirm_*) и выполняет соответствующее действие:
    - delete: показывает список событий для удаления
    - week: показывает план на 7 дней
    - back: возвращает в главное меню
    - delete_*: запрашивает подтверждение удаления выбранного события
    - confirm_*: подтверждает удаление и удаляет событие
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "delete":
        events = get_events_for_period(7)
        if not events:
            await query.edit_message_text("📭 Нет предстоящих событий для удаления.", reply_markup=get_main_keyboard())
        else:
            user_data[update.effective_user.id] = {"events": events}
            await query.edit_message_text("🗑 Выберите событие для удаления:", reply_markup=get_even ts_keyboard(events, "delete"))

    elif data == "week":
        events = get_events_for_period(7)
        if not events:
            await query.edit_message_text("📭 Нет событий на ближайшие 7 дней.", reply_markup=get_main_keyboard())
        else:
            message = "📅 *План на ближайшие 7 дней:*\n\n"
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                if "T" in start:
                    # Парсим UTC время и конвертируем в Пермь
                    if start.endswith('Z'):
                        start = start.replace('Z', '+00:00')
                    utc_time = datetime.datetime.fromisoformat(start)
                    perm_time = utc_to_local(utc_time)
                    date_str = perm_time.strftime("%d.%m.%Y")
                    time_str = perm_time.strftime("%H:%M")
                    message += f"📌 *{event['summary']}*\n   📅 {date_str} в {time_str}\n\n"
                else:
                    message += f"📌 *{event['summary']}*\n   📅 {start}\n\n"
            await query.edit_message_text(message, parse_mode="Markdown", reply_markup=get_back_keyboard())

    elif data == "back":
        await query.edit_message_text(
            "👋 Главное меню\n\n🗑 Удалить событие\n📅 Показать план на 7 дней\n📆 Открыть календарь \n\n📝 Добавить событие можно просто написав сообщение",
            reply_markup=get_main_keyboard()
        )

    elif data.startswith("delete_"):
        event_id = data.replace("delete_", "")
        events = user_data.get(update.effective_user.id, {}).get("events", [])
        event_to_delete = None
        for event in events:
            if event["id"] == event_id:
                event_to_delete = event
                break
        if event_to_delete:
            start = event_to_delete["start"].get("dateTime", event_to_delete["start"].get("date"))
            if "T" in start:
                if start.endswith('Z'):
                    start = start.replace('Z', '+00:00')
                utc_time = datetime.datetime.fromisoformat(start)
                perm_time = utc_to_local(utc_time)
                date_str = perm_time.strftime("%d.%m.%Y")
                time_str = perm_time.strftime("%H:%M")
                event_info = f"{event_to_delete['summary']} ({date_str} {time_str})"
            else:
                event_info = f"{event_to_delete['summary']} ({start})"
            keyboard = [[
                InlineKeyboardButton("✅ Да", callback_data=f"confirm_{event_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="back")
            ]]
            await query.edit_message_text(f"❓ Удалить событие?\n\n{event_info}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("confirm_"):
        event_id = data.replace("confirm_", "")
        success = delete_event_by_id(event_id)
        if success:
            await query.edit_message_text("✅ Событие успешно удалено!", reply_markup=get_main_keyboard())
        else:
            await query.edit_message_text("❌ Ошибка при удалении.", reply_markup=get_main_keyboard())


async def add_event_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстовых сообщений.
    Парсит текст через AI, извлекает название, дату и время, затем добавляет событие в Google Calendar.
    """
    text = update.message.text
    processing_msg = await update.message.reply_text("🤖 Обрабатываю...")
    title, start_time = parse_event(text, openai_client)
    if title and start_time:
        try:
            event_link, event_id = add_event_to_calendar(title, start_time)
            formatted_date = start_time.strftime("%d.%m.%Y")
            formatted_time = start_time.strftime("%H:%M")
            await processing_msg.edit_text(
                f"✅ Добавлено!\n\n📌 {title}\n📅 {formatted_date} в {formatted_time}",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            await processing_msg.edit_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())
    else:
        await processing_msg.edit_text(
            "❌ Не удалось распознать дату и время.\n\nПример: Встреча завтра в 15:30",
            reply_markup=get_main_keyboard()
        )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик голосовых сообщений.
    Скачивает голосовое сообщение, распознаёт его через Whisper, затем парсит полученный текст через AI и добавляет событие в календарь.
    """
    processing_msg = await update.message.reply_text("🎤 Обрабатываю голос...")
    try:
        audio_content = download_voice(update.message.voice.file_id, TELEGRAM_TOKEN)
        recognized_text = transcribe_voice(audio_content, openai_client)
        await processing_msg.edit_text(f"🎙️ Распознано: «{recognized_text}»")
        title, start_time = parse_event(recognized_text, openai_client)
        if title and start_time:
            event_link, event_id = add_event_to_calendar(title, start_time)
            formatted_date = start_time.strftime("%d.%m.%Y")
            formatted_time = start_time.strftime("%H:%M")
            await processing_msg.edit_text(
                f"✅ Добавлено!\n\n📌 {title}\n📅 {formatted_date} в {formatted_time}",
                reply_markup=get_main_keyboard()
            )
        else:
            await processing_msg.edit_text(
                "❌ Не удалось распознать дату и время\n\nПример: Встреча завтра в 15:30",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())


def main():
    """
    Главная функция запуска бота.
    Создаёт приложение, регистрирует обработчики команд, кнопок и сообщений,
    настраивает планировщик задач (ежедневная сводка в 7:00, проверка напоминаний каждые 30 минут)
    и запускает polling.
    """
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    job_queue = app.job_queue
    if job_queue:
        # Ежедневно в 7:00 по Перми (2:00 UTC)
        job_queue.run_daily(
            daily_report,
            time=datetime.time(hour=2, minute=0, second=0),
            days=tuple(range(7))
        )
        # Проверка напоминаний каждые 30 минут
        job_queue.run_repeating(check_reminders, interval=1800, first=60)

    print("🤖 Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()