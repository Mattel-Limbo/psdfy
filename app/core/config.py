from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # --- App ---
    APP_ENV: str = "development"  # development | staging | production
    APP_HOST: str = "localhost"
    APP_API_PORT: int = 3456
    APP_UI_PORT: int = 3457
    APP_LOG_LEVEL: str = "INFO"
    APP_REQUEST_TIMEOUT: int = 120
    
    # --- Limits ---
    MAX_UPLOAD_MB: int = 10
    MAX_IMAGE_DIM: int = 4096
    MAX_INFER_SIZE: int = 1536
    MIN_MASK_AREA_RATIO: float = 0.005
    
    # --- Auth: Client Signature ---
    SIGNATURE_SECRET_PEPPER: str = ""  # extra server-side pepper (optional|not mandatory)
    SIGNATURE_SALT_LENGTH: int = 10
    SIGNATURE_TTL_SECONDS: int = 86400  # 24 hours
    SIGNATURE_TIMESTAMP_SKEW: int = 300  # 5 minutes
    SIGNATURE_STORE: str = "memory"  # memory | sqlite | redis
    
    # --- Auth: Web UI password ---
    UI_PASSWORD: str = "123456"
    UI_SESSION_TTL_SECONDS: int = 86400
    UI_COOKIE_NAME: str = "psdfy_ui"
    
    # --- Storage ---
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_LOCAL_DIR: str = "./outputs"
    PUBLIC_BASE_URL: str = "http://localhost:3456"
    
    # --- CORS ---
    CORS_ALLOWED_ORIGINS: str = "*"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
