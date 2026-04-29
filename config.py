import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", 0))

NAVIDROME_URL = os.getenv("NAVIDROME_URL", "").rstrip("/")
NAVIDROME_USERNAME = os.getenv("NAVIDROME_USERNAME")
NAVIDROME_PASSWORD = os.getenv("NAVIDROME_PASSWORD")

MPV_SOCKET = os.getenv("MPV_SOCKET", "/tmp/mpvsocket")
