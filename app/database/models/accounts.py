"""
Account model for Datahive
"""

import random
from typing import Optional
from tortoise import Model, fields
from tortoise.expressions import Q


class Account(Model):
    """Account model for Datahive"""
    
    # Main fields
    email = fields.CharField(max_length=255, unique=True)
    email_password = fields.CharField(max_length=255, null=True)
    user_id = fields.CharField(max_length=255, null=True)
    imap_server = fields.CharField(max_length=255, null=True)
    
    # Tokens and codes
    auth_token = fields.CharField(max_length=2048, null=True)
    invite_code = fields.CharField(max_length=255, null=True)
    
    # Proxy
    active_account_proxy = fields.CharField(max_length=255, null=True)
    
    # Reverse relation to devices (created automatically via ForeignKey in Device)
    # devices: fields.ReverseRelation[Device] - accessible via account.devices

    class Meta:
        table = 'accounts'

    def __str__(self):
        return f"Account({self.email})"

    @classmethod
    async def get_account(cls, email: str):
        """Get account by email"""
        return await cls.get_or_none(email=email)

    @classmethod
    async def get_all_accounts(cls):
        """Get all accounts"""
        return await cls.all()

    @classmethod
    async def create_account(cls, *, email: str, email_password: str = None, 
                           auth_token: str = None, user_id: str = None, 
                           invite_code: str = None, imap_server: str = None):
        """Create a new account or update existing one"""
        account = await cls.get_account(email=email)
        
        if account is None:
            # Create new account
            return await cls.create(
                email=email,
                email_password=email_password,
                auth_token=auth_token,
                user_id=user_id,
                invite_code=invite_code,
                imap_server=imap_server
            )
        else:
            # Update existing account
            update_fields = []
            
            if email_password is not None:
                account.email_password = email_password
                update_fields.append('email_password')
                
            if auth_token is not None:
                account.auth_token = auth_token
                update_fields.append('auth_token')
                
            if user_id is not None:
                account.user_id = user_id
                update_fields.append('user_id')
                
            if invite_code is not None:
                account.invite_code = invite_code
                update_fields.append('invite_code')
                
            if imap_server is not None:
                account.imap_server = imap_server
                update_fields.append('imap_server')
                
            if update_fields:
                await account.save(update_fields=update_fields)
                
            return account

    async def update_account(self, *, email_password: str = None, auth_token: str = None, 
                           user_id: str = None, invite_code: str = None, imap_server: str = None):
        """Update account information"""
        update_fields = []
        
        if email_password is not None:
            self.email_password = email_password
            update_fields.append('email_password')
            
        if auth_token is not None:
            self.auth_token = auth_token
            update_fields.append('auth_token')
            
        if user_id is not None:
            self.user_id = user_id
            update_fields.append('user_id')
            
        if invite_code is not None:
            self.invite_code = invite_code
            update_fields.append('invite_code')
            
        if imap_server is not None:
            self.imap_server = imap_server
            update_fields.append('imap_server')
            
        if update_fields:
            await self.save(update_fields=update_fields)
            
        return self

    @classmethod
    async def get_auth_token(cls, email: str):
        """Get auth token for account by email"""
        account = await cls.get_account(email=email)
        if account:
            return account.auth_token
        return None

    @classmethod
    async def delete_account(cls, email: str):
        """Delete account by email"""
        account = await cls.get_account(email=email)
        if account:
            await account.delete()
            return True
        return False

    @classmethod
    async def get_random_invite_code(cls):
        """Get a random invite code from available ones"""
        codes = await cls.filter(~Q(invite_code=None)).values_list('invite_code', flat=True)
        codes = [c for c in codes if c]  # Filter out any None values
        if codes:
            return random.choice(codes)
        return None

    @classmethod
    async def collect_all_user_ids(cls):
        """Collect all user IDs from accounts"""
        ids = await cls.all().values_list('user_id', flat=True)
        return [i for i in ids if i]  # Filter out any None values
    
    @property
    def proxy(self) -> Optional[str]:
        """Get current proxy for account"""
        return self.active_account_proxy
    
    async def update_proxy(self, proxy: str) -> None:
        """Update proxy for this account"""
        self.active_account_proxy = proxy
        await self.save(update_fields=['active_account_proxy'])
