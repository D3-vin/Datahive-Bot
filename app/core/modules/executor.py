from typing import Optional

from app.core.base import Bot
from app.utils.logging import get_logger

logger = get_logger()


class ModuleExecutor:
    def __init__(self, email: str, email_password: str, imap_server: str, 
                 proxy: Optional[str] = None, account_index: Optional[int] = None):
        self.email = email
        self.email_password = email_password
        self.imap_server = imap_server
        self.bot = Bot(email, email_password, imap_server, proxy, account_index)
    
    async def process_registration(self):
        from app.core.modules.registration import RegistrationModule
        module = RegistrationModule(self.email, self.email_password, self.imap_server, self.bot)
        return await module.process()
    
    async def process_twitter_binding(self, twitter_tokens: list):
        from app.core.modules.twitter import TwitterBindingModule
        module = TwitterBindingModule(self.email, twitter_tokens, self.bot)
        return await module.process()
    
    async def process_farming(self):
        from app.core.modules.farming import FarmingModule
        module = FarmingModule(self.email, self.bot)
        return await module.process()

