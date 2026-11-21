"""
Discharge+ — Configuration
Loads all environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # Groq AI
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Discharge+"
    smtp_from_email: str = "noreply@dischargeplus.com"

    # 100ms Video
    hms_access_key: str = ""
    hms_secret: str = ""
    hms_template_id: str = ""

    # App
    app_name: str = "Discharge+"
    frontend_url: str = "https://dischargeplusai-poweredrecoveryplat.vercel.app"
    backend_url: str = "https://dischargeplus-ai-powered-recovery.onrender.com"
    environment: str = "development"

    # ML Feature Flags
    ml_enabled: bool = True
    ml_survey_recommender: bool = True
    ml_readmission: bool = True
    ml_anomaly: bool = True
    ml_hybrid_risk: bool = True
    ml_adherence: bool = True

    class Config:
        env_file = (str(Path(__file__).resolve().parent / ".env"), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
