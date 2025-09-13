import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SEATABLE_SERVER = os.getenv("SEATABLE_SERVER")
    SEATABLE_API_APP_TOKEN = os.getenv("SEATABLE_API_APP_TOKEN")
    SEATABLE_MAIN_MENU_ID = os.getenv("SEATABLE_MAIN_MENU_ID")
    SEATABLE_USERS_TABLE_ID = os.getenv("SEATABLE_USERS_TABLE_ID")
    SEATABLE_API_ATS_TOKEN = os.getenv("SEATABLE_API_ATS_TOKEN")
    SEATABLE_ATS_APP = os.getenv("SEATABLE_ATS_APP")
    SEATABLE_EMPLOYEE_BOOK_ID = os.getenv("SEATABLE_EMPLOYEE_BOOK_ID")

