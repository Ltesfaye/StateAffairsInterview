"""Configuration management"""

import os
from pathlib import Path
from typing import Optional
import yaml


class Config:
    """Application configuration"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Load configuration from YAML file and environment variables"""
        if config_path is None:
            # Default to config/config.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"
        
        self.config_path = config_path
        self._config = self._load_yaml(config_path)
        self._apply_env_overrides()
    
    def _load_yaml(self, config_path: Path) -> dict:
        """Load YAML configuration file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        # Database path
        if db_path := os.getenv("DATABASE_URL"):
            self._config.setdefault("database", {})["path"] = db_path
        
        # Log level
        if log_level := os.getenv("LOG_LEVEL"):
            self._config.setdefault("logging", {})["level"] = log_level
        
        # Output directory
        if output_dir := os.getenv("OUTPUT_DIRECTORY"):
            self._config.setdefault("download", {})["output_directory"] = output_dir
    
    @property
    def discovery(self) -> dict:
        """Discovery configuration"""
        return self._config.get("discovery", {})
    
    @property
    def download(self) -> dict:
        """Download configuration"""
        return self._config.get("download", {})
    
    @property
    def database(self) -> dict:
        """Database configuration"""
        return self._config.get("database", {})
    
    @property
    def logging(self) -> dict:
        """Logging configuration"""
        return self._config.get("logging", {})
    
    def get(self, key: str, default=None):
        """Get configuration value by dot-separated key"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load and return configuration"""
    return Config(config_path)

