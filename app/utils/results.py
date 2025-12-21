"""
Results system for Datahive
"""

import asyncio
import time
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional
from app.utils.logging import get_logger

logger = get_logger()


class ResultsManager:
    """Simple results manager like datahive"""
    
    def __init__(self, base_path: str = "./results"):
        self.base_path = Path(base_path)
        self.lock = asyncio.Lock()
        
        self.module_paths = {
            'registration': {
                "success": self.base_path / "registration" / "registration_success.txt",
                "failed": self.base_path / "registration" / "registration_failed.txt",
            }
        }
    
    async def setup_files(self) -> None:
        """Create necessary directories and files"""
        self.base_path.mkdir(exist_ok=True)
        
        for module_name, module_paths in self.module_paths.items():
            for path_key, path in module_paths.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    async with aiofiles.open(path, 'w'):
                        pass
    
    async def save_result(self, module: str, status: str, data: Dict[str, Any]) -> None:
        """Save result to appropriate file"""
        if module not in self.module_paths:
            logger.error(f"Unknown module: {module}")
            return
        
        if status not in self.module_paths[module]:
            logger.error(f"Unknown status '{status}' for module '{module}'")
            return
        
        file_path = self.module_paths[module][status]
        
        async with self.lock:
            try:
                async with aiofiles.open(file_path, 'a', encoding='utf-8') as file:
                    # Format: email:password or email only
                    if 'email' in data and data['email']:
                        if 'email_password' in data and data['email_password']:
                            line = f"{data['email']}:{data['email_password']}\n"
                        else:
                            line = f"{data['email']}\n"
                    elif 'private_key' in data and data['private_key']:
                        line = f"{data['private_key']}\n"
                    elif 'eth_address' in data:
                        line = f"{data['eth_address']}\n"
                    else:
                        line = f"{data}\n"
                    
                    await file.write(line)
                    
            except Exception as e:
                logger.error(f"Error writing result to {file_path}: {e}")
    
    async def save_registration_result(self, email: str, email_password: str, success: bool) -> None:
        """Save registration result - email:password format"""
        status = "success" if success else "failed"
        data = {
            'email': email,
            'email_password': email_password
        }
        await self.save_result('registration', status, data)
    
    



# Global results manager instance
_results_manager: Optional[ResultsManager] = None


def get_results_manager() -> ResultsManager:
    """Get global results manager instance"""
    global _results_manager
    if _results_manager is None:
        _results_manager = ResultsManager()
    return _results_manager


async def initialize_results() -> None:
    """Initialize results system"""
    manager = get_results_manager()
    await manager.setup_files()
    logger.debug("Results system initialized")