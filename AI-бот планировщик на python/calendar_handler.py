import datetime
import pytz
from calendar_auth import get_calendar_service
from ai_parser import parse_event_with_ai

TIMEZONE_STR = "Asia/Yekaterinburg"
TIMEZONE = pytz.timezone(TIMEZONE_STR)


def get_now_local():
    """Возвращает текущее время с часовым поясом Перми"""
    return datetime.datetime.now(TIMEZONE)


def get_now_utc():
    """Возвращает текущее время UTC"""
    return datetime.datetime.now(datetime.timezone.utc)


def local_to_utc(local_time):
    """Конвертирует пермское время в UTC"""
    return local_time.astimezone(datetime.timezone.utc)


def utc_to_local(utc_time):
    """Конвертирует UTC в пермское время"""
    return utc_time.astimezone(TIMEZONE)


def parse_event(text, openai_client=None):
    if not openai_client:
        return None, None
    try:
        result = parse_event_with_ai(text, openai_client)
        event_title = result.get("event")
        date_str = result.get("date")
        time_str = result.get("time")
        if not event_title or not date_str or not time_str:
            return None, None
        day, month, year = map(int, date_str.split('.'))
        hour, minute = map(int, time_str.split(':'))
        local_time = TIMEZONE.localize(datetime.datetime(year, month, day, hour, minute))
        return event_title, local_time
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None, None


def add_event_to_calendar(summary, start_time_local, end_time_local=None):
    """Добавляет событие, время указано в Перми"""
    service = get_calendar_service()
    if end_time_local is None:
        end_time_local = start_time_local + datetime.timedelta(hours=1)

    start_time_utc = local_to_utc(start_time_local)
    end_time_utc = local_to_utc(end_time_local)

    event = {
        "summary": summary,
        "start": {
            "dateTime": start_time_utc.isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": end_time_utc.isoformat(),
            "timeZone": "UTC"
        },
    }
    created_event = service.events().insert(calendarId="primary", body=event).execute()
    return created_event.get("htmlLink"), created_event.get("id")


def get_today_events():
    """Возвращает события на сегодня в пермском времени"""
    service = get_calendar_service()
    now_utc = get_now_utc()
    today_start_utc = datetime.datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
    today_end_utc = datetime.datetime(now_utc.year, now_utc.month, now_utc.day, 23, 59, 59, tzinfo=datetime.timezone.utc)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=today_start_utc.isoformat(),
        timeMax=today_end_utc.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        timeZone="UTC"
    ).execute()

    return events_result.get("items", [])


def get_upcoming_events(hours_ahead=168):
    """Возвращает события на ближайшие N часов (по умолчанию 7 дней)"""
    service = get_calendar_service()
    now_utc = get_now_utc()
    later_utc = now_utc + datetime.timedelta(hours=hours_ahead)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_utc.isoformat(),
        timeMax=later_utc.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        timeZone="UTC"
    ).execute()

    return events_result.get("items", [])


def get_events_for_period(days=7):
    """Возвращает события на ближайшие N дней"""
    service = get_calendar_service()
    now_utc = get_now_utc()
    end_date_utc = now_utc + datetime.timedelta(days=days)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_utc.isoformat(),
        timeMax=end_date_utc.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        timeZone="UTC"
    ).execute()

    events = events_result.get("items", [])

    # Конвертируем время событий в Пермь для отображения
    for event in events:
        start_str = event["start"].get("dateTime")
        if start_str:
            if start_str.endswith('Z'):
                start_str = start_str.replace('Z', '+00:00')
            utc_time = datetime.datetime.fromisoformat(start_str)
            local_time = utc_to_local(utc_time)
            event["start"]["dateTime"] = local_time.isoformat()

    return events


def delete_event_by_id(event_id):
    """Удаляет событие по ID"""
    try:
        service = get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True
    except Exception as e:
        print(f"Ошибка удаления: {e}")
        return False


def get_events_in_next_hour():
    """Возвращает события, которые начнутся в течение следующего часа (UTC)"""
    service = get_calendar_service()
    now_utc = get_now_utc()
    later_utc = now_utc + datetime.timedelta(hours=1)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_utc.isoformat(),
        timeMax=later_utc.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        timeZone="UTC"
    ).execute()

    return events_result.get("items", [])