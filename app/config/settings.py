"""
Configuration management for Datahive
"""

import os
import yaml
from typing import Optional, Dict, Any
from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger()


class DatahiveSettings:
    """Simple settings manager"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_path):
            logger.error(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file required: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                if not config_data:
                    raise ValueError("Config file is empty or invalid")
                return config_data
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    @property
    def registration_threads(self) -> int:
        """Number of threads for registration"""
        return self.data.get("threads", {}).get("registration", 5)
    
    @property
    def farming_threads(self) -> int:
        """Number of threads for farming"""
        return self.data.get("threads", {}).get("farming", 3)
    
    @property
    def threads(self) -> int:
        """Number of threads (backward compatibility)"""
        return self.registration_threads
    
    @property
    def logging_level(self) -> str:
        """Logging level"""
        return self.data.get("logging", {}).get("level", "INFO")
    
    @property
    def delay_min(self) -> int:
        """Minimum delay"""
        return self.data["delay_before_start"]["min"]
    
    @property
    def delay_max(self) -> int:
        """Maximum delay"""
        return self.data["delay_before_start"]["max"]
    
    @property
    def referral_code_settings(self) -> Dict[str, Any]:
        """Referral code settings"""
        return self.data.get("referral_code_settings", {})
    
    @property
    def use_random_ref_code_from_db(self) -> bool:
        """Use random referral code from database"""
        return self.referral_code_settings.get("use_random_ref_code_from_db", True)
    
    @property
    def static_referral_code(self) -> Optional[str]:
        """Static referral code from config"""
        code = self.referral_code_settings.get("static_referral_code", "")
        return code.strip() if code else None
    
    @property
    def retry_delay(self) -> int:
        """Retry delay in seconds"""
        return self.data.get("retry", {}).get("delay_seconds", 5)
    
    @property
    def proxy_rotation_enabled(self) -> bool:
        """Whether to enable proxy rotation on retry exhaustion"""
        return self.data.get("retry", {}).get("proxy_rotation", True)
    
    @property
    def multiprocess_farming_enabled(self) -> bool:
        """Whether multiprocess farming is enabled"""
        return self.data.get("multiprocess_farming", {}).get("enabled", True)
    
    @property
    def multiprocess_max_processes(self) -> int:
        """Maximum number of processes for multiprocess farming"""
        return self.data.get("multiprocess_farming", {}).get("max_processes", 0)
    
    @property
    def imap_settings(self) -> Dict[str, Any]:
        """IMAP settings"""
        return self.data.get("imap_settings", {})
    
    @property
    def use_proxy_for_imap(self) -> bool:
        """Use proxy for IMAP connections"""
        return self.imap_settings.get("use_proxy_for_imap", False)
    
    @property
    def redirect_settings(self) -> Dict[str, Any]:
        """Redirect email settings (optional)"""
        return self.data.get("redirect_settings", {})
    
    @property
    def redirect_enabled(self) -> bool:
        """Whether redirect email is enabled"""
        return self.redirect_settings.get("enable", False)
    
    @property
    def max_registration_attempts(self) -> int:
        """Maximum registration attempts"""
        return self.data.get("retry", {}).get("max_registration_attempts", 3)
    
    @property
    def max_farm_attempts(self) -> int:
        """Maximum farm attempts"""
        return self.data.get("retry", {}).get("max_farm_attempts", 3)
    
    @property
    def email_validation_timeout(self) -> int:
        """Email validation timeout in seconds"""
        return self.imap_settings.get("timeout", 30)
    
    @property
    def farm_settings(self) -> Dict[str, Any]:
        """Farm settings"""
        return self.data.get("farm_settings", {
            "max_devices_per_batch": 200,
            "max_concurrent_tasks": 200,
            "device_task_timeout": 60
        })
    
    @property
    def device_settings(self) -> Dict[str, Any]:
        """Device settings"""
        return self.data.get("device_settings", {
            "active_devices_per_account": {
                "min": 1,
                "max": 1
            }
        })


# Global settings instance
_settings_instance: Optional[DatahiveSettings] = None


def get_settings() -> DatahiveSettings:
    """Get global settings instance"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = DatahiveSettings()
    return _settings_instance