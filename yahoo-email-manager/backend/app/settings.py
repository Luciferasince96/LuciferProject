import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

@dataclass(frozen=True)
class Settings:
    yahoo_email: str = os.getenv('YAHOO_EMAIL', '').strip()
    yahoo_password: str = os.getenv('YAHOO_APP_PASSWORD', '').strip()
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '').strip()
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini').strip()

settings = Settings()
