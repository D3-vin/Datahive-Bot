import asyncio
import random
from typing import Optional, List, Dict, Any

from app.database.models.accounts import Account
from app.utils.logging import get_logger

logger = get_logger()


class DatabaseManager:
    def __init__(self):
        self.initialized = False
    
    async def init(self) -> None:
        if self.initialized:
            return
        
        from app.database.settings import initialize_database
        await initialize_database()
        self.initialized = True
    
    async def save_account(
        self, 
        email: str,
        email_password: Optional[str] = None,
        user_id: Optional[str] = None,
        auth_token: Optional[str] = None, 
        invite_code: Optional[str] = None,
        imap_server: Optional[str] = None
    ) -> bool:
        try:
            account = await Account.get_or_none(email=email)
            
            if account is None:
                account = await Account.create(
                    email=email,
                    email_password=email_password,
                    user_id=user_id,
                    auth_token=auth_token,
                    invite_code=invite_code,
                    imap_server=imap_server
                )
            else:
                if email_password is not None:
                    account.email_password = email_password
                if user_id is not None:
                    account.user_id = user_id
                if auth_token is not None:
                    account.auth_token = auth_token
                if invite_code is not None:
                    account.invite_code = invite_code
                if imap_server is not None:
                    account.imap_server = imap_server
                await account.save()
            
            return True
        except Exception as e:
            logger.error(f"Failed to save account: {e}")
            return False
    
    async def get_account(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            account = await Account.get_or_none(email=email)
            if account:
                return {
                    "id": account.id,
                    "email": account.email,
                    "email_password": account.email_password,
                    "user_id": account.user_id,
                    "auth_token": account.auth_token,
                    "invite_code": account.invite_code,
                    "imap_server": account.imap_server
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return None
    
    async def save_token(self, email: str, auth_token: str) -> bool:
        try:
            account = await Account.get_or_none(email=email)
            if account:
                account.auth_token = auth_token
                await account.save()
            else:
                await Account.create(
                    email=email,
                    auth_token=auth_token
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            return False
    
    async def get_token(self, email: str) -> Optional[str]:
        try:
            account = await Account.get_or_none(email=email)
            return account.auth_token if account else None
        except Exception as e:
            logger.error(f"Failed to get token: {e}")
            return None
    
    async def get_random_invite_code(self) -> Optional[str]:
        try:
            accounts = await Account.filter(invite_code__isnull=False).all()
            if accounts:
                random_account = random.choice(accounts)
                return random_account.invite_code
            return None
        except Exception as e:
            logger.error(f"Failed to get random invite code: {e}")
            return None
    
    async def get_all_accounts(self) -> List[Dict[str, Any]]:
        try:
            accounts = await Account.all()
            return [
                {
                    "id": account.id,
                    "email": account.email,
                    "email_password": account.email_password,
                    "user_id": account.user_id,
                    "auth_token": account.auth_token,
                    "invite_code": account.invite_code,
                    "imap_server": account.imap_server
                }
                for account in accounts
            ]
        except Exception as e:
            logger.error(f"Failed to get all accounts: {e}")
            return []
    
    async def get_accounts_count(self) -> int:
        try:
            return await Account.all().count()
        except Exception as e:
            logger.error(f"Failed to get accounts count: {e}")
            return 0
    
    async def get_all_accounts_with_tokens(self) -> List[Dict[str, Any]]:
        try:
            accounts = await Account.filter(auth_token__isnull=False).all()
            return [
                {
                    "id": account.id,
                    "email": account.email,
                    "email_password": account.email_password,
                    "user_id": account.user_id,
                    "auth_token": account.auth_token,
                    "invite_code": account.invite_code,
                    "imap_server": account.imap_server,
                    "twitter_bound": False
                }
                for account in accounts
            ]
        except Exception as e:
            logger.error(f"Failed to get accounts with tokens: {e}")
            return []
    
    @staticmethod
    async def create_account_from_data(account_data: Dict) -> Account:
        try:
            account = await Account.create_account(
                email=account_data.get('email'),
                email_password=account_data.get('email_password'),
                user_id=account_data.get('user_id'),
                auth_token=account_data.get('auth_token'),
                invite_code=account_data.get('invite_code'),
                imap_server=account_data.get('imap_server')
            )
            logger.debug(f"Created/updated account: {account.email}")
            return account
        except Exception as e:
            logger.error(f"Error creating account: {e}")
            raise
    


_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


async def init_database() -> None:
    db = get_db()
    await db.init()


async def close_database() -> None:
    pass

