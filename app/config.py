"""Application settings loaded from environment variables / .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Security
    cookie_secure: bool = False  # set True in production (behind HTTPS)
    session_lifetime_days: int = 30

    # Alerts / jobs
    refresh_interval_hours: int = 24
    job_retention_days: int = 7
    min_score: int = 10
    max_jobs_per_alert_refresh: int = 200

    # Database
    database_url: str = f"sqlite:///{DATA_DIR / 'oppfinder.db'}"

    # Job board providers (optional API keys - free registration)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    ft_client_id: str = ""
    ft_client_secret: str = ""

    # AI assistant (optional - chat is disabled when no key is set)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
