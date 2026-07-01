import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "BuildWise Aether"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "MOCK_KEY_IF_ABSENT")
    GEMINI_MODEL: str = "gemini-2.5-pro"  # Use updated model profiles securely
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()