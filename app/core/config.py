from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and config.toml."""
    
    # --- App ---
    APP_ENV: str = "development"  # development | staging | production
    APP_HOST: str = "localhost"
    APP_API_PORT: int = 3456
    APP_UI_PORT: int = 3457
    APP_LOG_LEVEL: str = "INFO"
    APP_REQUEST_TIMEOUT: int = 120
    CONVERT_TIMEOUT: int = 600  # SAM2 on CPU can take several minutes

    # SAM2 automatic mask generator tuning.
    # Lower points_per_side = fewer sample points = much faster on CPU.
    # Default SAM2 value is 32 (1024 points). 16 = 256 points, ~4x faster.
    SAM2_POINTS_PER_SIDE: int = 16
    SAM2_PRED_IOU_THRESH: float = 0.88
    SAM2_STABILITY_SCORE_THRESH: float = 0.95
    SAM2_MIN_MASK_REGION_AREA: int = 100
    
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
    
    # --- Models ---
    ENABLE_SAM2: bool = True
    ENABLE_GROUNDING_DINO: bool = False
    DEVICE: str = "cpu"  # cpu, cuda, mps
    DINO_WEIGHTS_PATH: Optional[str] = None
    SAM2_WEIGHTS_PATH: Optional[str] = None
    
    # --- Client Secret (from config.toml [auth] section) ---
    CLIENT_SECRET: str = ""
    
    model_config = ConfigDict(env_file=".env", case_sensitive=True)


def _load_config_from_toml() -> dict:
    """Load settings from ~/.psdfy/config.toml if it exists."""
    config_file = Path.home() / ".psdfy" / "config.toml"
    
    if not config_file.exists():
        return {}
    
    # Simple TOML parser for [models] and [auth] sections
    config = {}
    current_section = None
    
    try:
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                elif "=" in line and current_section in ("models", "auth", "app"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    # Strip inline comments, then quotes
                    value = value.split("#")[0].strip().strip('"').strip("'")
                    
                    # Parse boolean values
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    config[f"{current_section}.{key}"] = value
    except Exception:
        pass
    
    return config


def _create_settings() -> Settings:
    """Create settings instance with TOML config overrides."""
    settings = Settings()
    
    # Load overrides from config.toml
    toml_config = _load_config_from_toml()
    
    if "models.enable_sam2" in toml_config:
        settings.ENABLE_SAM2 = toml_config["models.enable_sam2"]
    
    if "models.enable_grounding_dino" in toml_config:
        settings.ENABLE_GROUNDING_DINO = toml_config["models.enable_grounding_dino"]
    
    if "models.dino_weights_path" in toml_config:
        settings.DINO_WEIGHTS_PATH = toml_config["models.dino_weights_path"]
    
    if "models.sam2_weights_path" in toml_config:
        settings.SAM2_WEIGHTS_PATH = toml_config["models.sam2_weights_path"]
    
    if "auth.client_secret" in toml_config:
        settings.CLIENT_SECRET = toml_config["auth.client_secret"]
    
    if "auth.signature_pepper" in toml_config:
        settings.SIGNATURE_SECRET_PEPPER = toml_config["auth.signature_pepper"]
    
    # app section
    if "app.host" in toml_config:
        settings.APP_HOST = toml_config["app.host"]
    
    if "app.api_port" in toml_config:
        settings.APP_API_PORT = toml_config["app.api_port"]
    
    if "app.ui_port" in toml_config:
        settings.APP_UI_PORT = toml_config["app.ui_port"]
    
    if "app.device" in toml_config:
        settings.DEVICE = toml_config["app.device"]
    
    if "app.log_level" in toml_config:
        settings.APP_LOG_LEVEL = toml_config["app.log_level"]
    
    return settings


settings = _create_settings()
