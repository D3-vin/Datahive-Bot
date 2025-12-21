"""
Device model for Datahive farming
"""

from datetime import datetime
import random
from typing import Optional
from tortoise import Model, fields


class Device(Model):
    """Device model for farming"""
    
    # Account relationship
    account = fields.ForeignKeyField('models.Account', related_name='devices')
    
    # Device information
    user_agent = fields.CharField(max_length=512)
    cpu_architecture = fields.CharField(max_length=128)
    cpu_model = fields.CharField(max_length=256)
    cpu_processor_count = fields.IntField()
    device_id = fields.CharField(max_length=256, unique=True)
    device_os = fields.CharField(max_length=128)
    
    # Farming timestamps
    next_ping_at = fields.DatetimeField(null=True)
    next_task_request_at = fields.DatetimeField(null=True)
    
    # Device proxy
    active_device_proxy = fields.CharField(max_length=255, null=True)

    class Meta:
        table = 'devices'

    def __str__(self):
        return f"Device({self.device_id[:8]}... for {self.account.email if self.account else 'None'})"

    @classmethod
    async def create_device_for_account(
        cls,
        *,
        account,
        user_agent: str,
        cpu_architecture: str,
        cpu_model: str,
        cpu_processor_count: int,
        device_os: str,
        device_id: str,
        active_device_proxy: str = None
    ):
        """Create or update a device associated with an account"""
        device = await cls.get_or_none(device_id=device_id)
        
        if device is None:
            device = await cls.create(
                account=account,
                user_agent=user_agent,
                cpu_architecture=cpu_architecture,
                cpu_model=cpu_model,
                cpu_processor_count=cpu_processor_count,
                device_id=device_id,
                device_os=device_os,
                active_device_proxy=active_device_proxy
            )
        else:
            device.account = account
            device.user_agent = user_agent
            device.cpu_architecture = cpu_architecture
            device.cpu_model = cpu_model
            device.cpu_processor_count = cpu_processor_count
            device.device_os = device_os
            device.active_device_proxy = active_device_proxy
            await device.save()
        
        return device

    @classmethod
    async def get_devices_for_account(cls, account):
        """Get all devices for a specific account"""
        return await cls.filter(account=account).all()

    @classmethod
    async def get_devices_with_limit(cls, account, limit: int):
        """Get devices for account with a limit"""
        return await cls.filter(account=account).limit(limit).all()

    @classmethod
    async def get_random_device_for_account(cls, account):
        """Get a random device for an account"""
        devices = await cls.get_devices_for_account(account)
        if devices:
            return random.choice(devices)
        return None

    @classmethod
    async def get_device_by_id(cls, device_id: str):
        """Get device by device_id"""
        return await cls.get_or_none(device_id=device_id)

    async def update_device_proxy(self, proxy: str):
        """Update proxy for this device"""
        self.active_device_proxy = proxy
        await self.save(update_fields=['active_device_proxy'])
        return self

    async def update_device(
        self,
        user_agent: Optional[str] = None,
        cpu_architecture: Optional[str] = None,
        cpu_model: Optional[str] = None,
        cpu_processor_count: Optional[int] = None,
        device_os: Optional[str] = None,
        active_device_proxy: Optional[str] = None,
        next_ping_at: Optional[datetime] = None,
        next_task_request_at: Optional[datetime] = None
    ):
        """Update device information"""
        update_fields = []
        
        if user_agent is not None:
            self.user_agent = user_agent
            update_fields.append('user_agent')
            
        if cpu_architecture is not None:
            self.cpu_architecture = cpu_architecture
            update_fields.append('cpu_architecture')
            
        if cpu_model is not None:
            self.cpu_model = cpu_model
            update_fields.append('cpu_model')
            
        if cpu_processor_count is not None:
            self.cpu_processor_count = cpu_processor_count
            update_fields.append('cpu_processor_count')
            
        if device_os is not None:
            self.device_os = device_os
            update_fields.append('device_os')
            
        if active_device_proxy is not None:
            self.active_device_proxy = active_device_proxy
            update_fields.append('active_device_proxy')
            
        if next_ping_at is not None:
            self.next_ping_at = next_ping_at
            update_fields.append('next_ping_at')
            
        if next_task_request_at is not None:
            self.next_task_request_at = next_task_request_at
            update_fields.append('next_task_request_at')
        
        if update_fields:
            await self.save(update_fields=update_fields)
        
        return self

    @classmethod
    async def bulk_update_devices(cls, devices: list, fields: list):
        """Bulk update devices"""
        if not devices:
            return
        
        for device in devices:
            await device.save(update_fields=fields)

