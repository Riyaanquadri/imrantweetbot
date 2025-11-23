from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    X_BEARER_TOKEN = os.getenv('X_BEARER_TOKEN')
    X_API_KEY = os.getenv('X_API_KEY')
    X_API_SECRET = os.getenv('X_API_SECRET')
    X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
    X_ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')

    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    BOT_HANDLE = os.getenv('BOT_HANDLE', 'bot')
    PROJECT_KEYWORDS = [k.strip() for k in os.getenv('PROJECT_KEYWORDS', '').split(',') if k.strip()]

    POST_INTERVAL_HOURS = int(os.getenv('POST_INTERVAL_HOURS', '3'))
    MENTION_POLL_MINUTES = int(os.getenv('MENTION_POLL_MINUTES', '1'))

    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() in ('1','true','yes')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
