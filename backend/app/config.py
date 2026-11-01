import os
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bolti_bahi.db")
