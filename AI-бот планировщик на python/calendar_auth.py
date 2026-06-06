import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDS_FILE = "/my_planner_bot/credentials.json"
TOKEN_FILE = "/my_planner_bot/token.pickle"


def get_calendar_service():
    '''
    Возвращает объект сервиса Google Calendar, через который можно выполнять операции (добавлять, удалять, получать события)
    '''
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Обновление токена...")
            creds.refresh(Request())
        else:
            print("\n" + "="*60)
            print("🔐 АВТОРИЗАЦИЯ GOOGLE CALENDAR")
            print("="*60 + "\n")

            # Используем flow с явным указанием redirect_uri
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_FILE,
                SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"  # Ключевой параметр!
            )

            # Получаем URL для авторизации
            auth_url, _ = flow.authorization_url(
                prompt='consent',
                access_type='offline'
            )

            print("1️⃣  Перейдите по ссылке в браузере НА ВАШЕМ КОМПЬЮТЕРЕ:")
            print("\n" + auth_url + "\n")
            print("2️⃣  Войдите в аккаунт")
            print("3️⃣  Разрешите доступ")
            print("4️⃣  Вы увидите код (например: 4/0AQSTgQExxx...)")
            print("5️⃣  Скопируйте этот код и вставьте сюда\n")

            # Просим ввести код
            code = input("👉 Вставьте код и нажмите Enter: ").strip()

            # Обмениваем код на токены
            flow.fetch_token(code=code)
            creds = flow.credentials

            print("\n✅ Авторизация успешна!")

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("calendar", "v3", credentials=creds)


if __name__ == "__main__":
    service = get_calendar_service()
    if service:
        print("✅ Google Calendar готов к работе!")