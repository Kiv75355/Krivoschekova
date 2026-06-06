import json
import datetime
from openai import OpenAI


def parse_event_with_ai(text, openai_client):
    """
    Использует GPT для извлечения события из текста
    """
    now = datetime.datetime.now()
    today = now.strftime("%d.%m.%Y")
    today_weekday = now.strftime("%A")
    current_time = now.strftime("%H:%M")

    weekdays_ru = {
        "Monday": "понедельник",
        "Tuesday": "вторник",
        "Wednesday": "среда",
        "Thursday": "четверг",
        "Friday": "пятница",
        "Saturday": "суббота",
        "Sunday": "воскресенье"
    }
    today_weekday_ru = weekdays_ru[today_weekday]

    # Вычисляем даты для дней недели
    days_map = {}
    for i in range(7):
        future_date = now + datetime.timedelta(days=i)
        weekday_en = future_date.strftime("%A")
        weekday_ru = weekdays_ru[weekday_en]
        days_map[weekday_ru] = future_date.strftime("%d.%m.%Y")

    # Завтра и послезавтра
    tomorrow = (now + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
    day_after_tomorrow = (now + datetime.timedelta(days=2)).strftime("%d.%m.%Y")

    prompt = f"""
Сегодня: {today} ({today_weekday_ru})
Текущее время: {current_time}
Завтра: {tomorrow}
Послезавтра: {day_after_tomorrow}

Даты предстоящих дней:
- понедельник: {days_map.get('понедельник', 'неизвестно')}
- вторник: {days_map.get('вторник', 'неизвестно')}
- среда: {days_map.get('среда', 'неизвестно')}
- четверг: {days_map.get('четверг', 'неизвестно')}
- пятница: {days_map.get('пятница', 'неизвестно')}
- суббота: {days_map.get('суббота', 'неизвестно')}
- воскресенье: {days_map.get('воскресенье', 'неизвестно')}

ВАЖНЫЕ ПРАВИЛА (строго соблюдай приоритет):
1. Если пользователь сказал "сегодня" — используй ТОЛЬКО сегодняшнюю дату ({today})
2. Если пользователь сказал "завтра" — используй ТОЛЬКО завтрашнюю дату ({tomorrow})
3. Если пользователь сказал "послезавтра" — используй ТОЛЬКО дату через 2 дня ({day_after_tomorrow})
4. Если пользователь назвал день недели (понедельник, вторник и т.д.) — найди БЛИЖАЙШУЮ такую дату из списка выше
5. Если пользователь назвал число (например, "8 июня") — используй эту дату
6. Слова "сегодня", "завтра", "послезавтра" и дни недели имеют ПРИОРИТЕТ над числами

Правила перевода времени:
- "8,00" или "8:00" или "8.00" или "8 часов" = 08:00
- "9 часов вечера" = 21:00
- "9 часов утра" = 09:00
- "половина пятого" = 16:30
- "без четверти три" = 14:45
- "7 вечера" = 19:00
- "8 вечера" = 20:00

Текст пользователя: "{text}"

Ответь строго в формате JSON (только JSON, без пояснений):
{{"event": "название события", "date": "ДД.ММ.ГГГГ", "time": "ЧЧ:ММ"}}

Примеры правильных ответов:
"встреча завтра в 15:30" -> {{"event": "встреча", "date": "{tomorrow}", "time": "15:30"}}
"проверка завтра на 8,00" -> {{"event": "проверка", "date": "{tomorrow}", "time": "08:00"}}
"в пятницу встреча с Катей в 9 часов вечера" -> {{"event": "встреча с Катей", "date": "{days_map.get('пятница', 'неизвестно')}", "time": "21:00"}}
"""

    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    result = json.loads(response.choices[0].message.content)
    return result


if __name__ == "__main__":
    # Тест
    import os
    from dotenv import load_dotenv
    load_dotenv("/my_planner_bot/.env")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    test_text = "проверка завтра на 8,00"
    print(f"\n🔍 Тестируем текст: {test_text}\n")
    result = parse_event_with_ai(test_text, client)
    print(f"📊 Результат: {result}")