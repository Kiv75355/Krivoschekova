import datetime
import json
import os
import asyncio
from dotenv import load_dotenv
from calendar_handler import get_today_events, get_upcoming_events
from zoneinfo import ZoneInfo

TIMEZONE = "Asia/Yekaterinburg"
sent_reminders_file = "/my_planner_bot/sent_reminders.json"


def get_chat_id():
    """Получает chat_id из .env файла"""
    load_dotenv("/my_planner_bot/.env")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if chat_id:
        return int(chat_id)
    return None


def load_sent_reminders():
    """Загружает список ID событий, на которые уже отправлены напоминания"""
    if os.path.exists(sent_reminders_file):
        try:
            with open(sent_reminders_file, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_sent_reminder(event_id):
    """Сохраняет ID события как отправленное"""
    sent = load_sent_reminders()
    sent.add(event_id)
    with open(sent_reminders_file, "w") as f:
        json.dump(list(sent), f)


def clear_sent_reminders():
    """Очищает список отправленных напоминаний"""
    if os.path.exists(sent_reminders_file):
        os.remove(sent_reminders_file)
        print("✅ Очищен список отправленных напоминаний")


async def daily_report(context):
    """Отправляет список дел на сегодня в 7:00"""
    chat_id = get_chat_id()
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID не найден")
        return

    events = get_today_events()

    if not events:
        await context.bot.send_message(chat_id, "🌅 Доброе утро! На сегодня нет запланированных событий.")
        return

    message = "🌅 *Ваш план на сегодня:*\n\n"
    for event in events:
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        if start_str and "T" in start_str:
            # Парсим время
            start = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            start_local = start.astimezone(ZoneInfo(TIMEZONE))
            time_str = start_local.strftime("%H:%M")
            message += f"• {event['summary']} — в {time_str}\n"
        else:
            message += f"• {event['summary']} — целый день\n"

    await context.bot.send_message(chat_id, message, parse_mode="Markdown")

    # Очищаем список отправленных напоминаний в начале дня
    clear_sent_reminders()


async def check_reminders(context):
    """
    Проверяет события и отправляет ОДНО напоминание со всеми событиями,
    которые начнутся через час (диапазон 45-75 минут).
    При ошибках делает до 3 попыток с задержкой 5 секунд.
    """
    chat_id = get_chat_id()
    if not chat_id:
        return

    for attempt in range(3):
        try:
            now = datetime.datetime.now(ZoneInfo(TIMEZONE))
            # Смотрим события на 2 часа вперёд
            events = get_upcoming_events(hours_ahead=2)
            sent = load_sent_reminders()

            # Собираем события, которые будут через час (45-75 минут)
            upcoming_events = []
            for event in events:
                event_id = event["id"]
                if event_id in sent:
                    continue

                start_str = event["start"].get("dateTime")
                if not start_str:
                    continue

                # Парсим время начала
                start = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                start_local = start.astimezone(ZoneInfo(TIMEZONE))
                minutes_until = (start_local - now).total_seconds() / 60

                if 45 <= minutes_until <= 75:
                    upcoming_events.append({
                        "title": event.get("summary", "Событие"),
                        "time": start_local.strftime("%H:%M"),
                        "id": event_id
                    })

            # Отправляем ОДНО сообщение со всеми событиями
            if upcoming_events:
                if len(upcoming_events) == 1:
                    e = upcoming_events[0]
                    message = f"⏰ *Напоминание!*\n\nЧерез час: *{e['title']}*\n🕐 в {e['time']}"
                else:
                    message = f"⏰ *Напоминания на ближайший час!*\n\n"
                    for e in upcoming_events:
                        message += f"• *{e['title']}* — в {e['time']}\n"

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown"
                )

                # Сохраняем ID всех отправленных событий
                for e in upcoming_events:
                    save_sent_reminder(e["id"])
                    print(f"✅ Напоминание о {e['title']} в {e['time']}")

            break  # Успешно, выходим из цикла retry

        except Exception as e:
            print(f"❌ Ошибка в check_reminders (попытка {attempt+1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(5)  # Ждём 5 секунд перед следующей попыткой
            else:
                print("❌ check_reminders не сработала после 3 попыток")