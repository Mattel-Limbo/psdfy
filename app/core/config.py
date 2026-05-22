from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    APP_HOST: str = "localhost"
    APP_API_PORT: int = 3456
    APP_UI_PORT: int = 3457
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
