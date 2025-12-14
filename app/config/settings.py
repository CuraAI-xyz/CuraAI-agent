import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_USERNAME = os.getenv("SUPABASE_USERNAME")
    SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD")
    
    # Email
    EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
    
    # Google Calendar
    CREDENTIALS_JSON = os.getenv("CREDENTIALS_JSON")
    
    # Audio
    AUDIO_SAMPLE_RATE = 16000
    
    @property
    def db_connection(self):
        if self.SUPABASE_USERNAME and self.SUPABASE_PASSWORD:
            return f"postgresql://{self.SUPABASE_USERNAME}:{self.SUPABASE_PASSWORD}@<host>:<port>/UsersData"
        return None

settings = Settings()

