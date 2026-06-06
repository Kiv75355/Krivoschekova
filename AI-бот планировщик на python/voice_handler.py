import os
import requests
from openai import OpenAI

# Папка для временных файлов
TEMP_DIR = "/tmp/bot_audio"
os.makedirs(TEMP_DIR, exist_ok=True)


def download_voice(file_id, bot_token):
    """Скачивает голосовое сообщение от Telegram"""
    url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    response = requests.get(url).json()

    file_path = response["result"]["file_path"]
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    audio_content = requests.get(download_url).content

    return audio_content


def transcribe_voice(audio_content, openai_client):
    """Отправляет голос в Whisper и возвращает текст"""
    temp_file = os.path.join(TEMP_DIR, "voice.ogg")

    with open(temp_file, "wb") as f:
        f.write(audio_content)

    with open(temp_file, "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru"
        )

    os.remove(temp_file)
    return transcript.text