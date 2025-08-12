import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SEATABLE_API_TOKEN = os.getenv("SEATABLE_API_TOKEN")
    SEATABLE_SERVER = os.getenv("SEATABLE_SERVER")
    SEATABLE_MAIN_MENU_ID = os.getenv("SEATABLE_MAIN_MENU_ID")