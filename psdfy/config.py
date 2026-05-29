"""Configuration management for psdfy."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
import uuid
from psdfy import __version__


class ConfigManager:
    """Manages ~/.psdfy/config.toml configuration."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_dir: Config directory (default: ~/.psdfy)
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".psdfy"
        
        self.config_file = self.config_dir / "config.toml"
        self.weights_dir = self.config_dir / "weights"
        self.outputs_dir = self.config_dir / "outputs"
        self.run_dir = self.config_dir / "run"
    
    def ensure_directories(self) -> None:
        """Create necessary directories."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.weights_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir.mkdir(parents=True, exist_ok=True)
    
    def create_default_config(
        self,
        password: str = "123456",
        host: str = "localhost",
        api_port: int = 3456,
        ui_port: int = 3457,
        enable_sam2: bool = True,
    ) -> str:
        """
        Create default config.toml content.
        
        Args:
            password: UI password
            host: API host
            api_port: API port
            ui_port: UI port
            enable_sam2: Enable SAM2 model
            
        Returns:
            Config file content
        """
        import hashlib
        import bcrypt
        
        # Hash password with bcrypt
        password_hash = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt()
        ).decode()
        
        # Generate secrets
        client_secret = str(uuid.uuid4())
        signature_pepper = os.urandom(32).hex()
        
        config = f"""# Psdfy Configuration
# Generated automatically by 'psdfy install'

[app]
host = "{host}"
api_port = {api_port}
ui_port = {ui_port}
device = "cpu"  # cpu, cuda, mps
log_level = "INFO"

[auth]
ui_password_hash = "{password_hash}"
client_secret = "{client_secret}"
signature_pepper = "{signature_pepper}"
signature_ttl_seconds = 86400

[models]
sam2_weights_path = "{self.weights_dir}/sam2_hiera_large.pt"
enable_sam2 = {"true" if enable_sam2 else "false"}
enable_grounding_dino = true
dino_weights_path = "{self.weights_dir}/groundingdino_swint_ogc.pth"

[storage]
backend = "local"
local_dir = "{self.outputs_dir}"

[meta]
version = "{__version__}"
installed_at = "{__import__('datetime').datetime.now().isoformat()}"
"""
        return config
    
    def save_config(self, content: str) -> None:
        """Save config to file."""
        self.ensure_directories()
        with open(self.config_file, "w") as f:
            f.write(content)
    
    def load_config(self) -> Dict[str, Any]:
        """Load config from file."""
        if not self.config_file.exists():
            return {}
        
        # Simple TOML parser (for MVP)
        config = {}
        current_section = None
        
        with open(self.config_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    config[current_section] = {}
                elif "=" in line and current_section:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    
                    # Parse boolean values
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    # Try to parse as int
                    elif value.isdigit():
                        value = int(value)
                    
                    config[current_section][key] = value
        
        return config
    
    def get_config_value(self, section: str, key: str, default: Any = None) -> Any:
        """Get config value."""
        config = self.load_config()
        return config.get(section, {}).get(key, default)


def get_config_manager() -> ConfigManager:
    """Get config manager instance."""
    return ConfigManager()
