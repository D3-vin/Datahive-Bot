import asyncio
from typing import Optional

from app.core.base import Bot
from app.database.models.accounts import Account
from app.database.models.devices import Device
from app.utils.logging import get_logger
from app.utils.shutdown import is_shutdown_requested
from app.utils.sleep import get_sleep_until, verify_sleep

logger = get_logger()


class FarmingModule:
    """Farming module based on HTTP API"""
    
    def __init__(self, email: str, bot: Bot):
        self.email = email
        self.bot = bot
    
    async def process(self) -> None:
        """Main farming loop"""
        await self.bot.db.init()
        
        account = await Account.get_account(self.email)
        if not account:
            logger.error("Account not found in database", self.email)
            return
        
        if not account.auth_token:
            logger.error("Account not logged in. Please login first.", self.email)
            return
        
        devices = await Device.get_devices_for_account(account)
        if not devices:
            logger.warning("No devices found for account. Devices will be created during first farming cycle.", self.email)
            return
        
        logger.info(f"Starting farming for {len(devices)} device(s)", self.email)
        
        while self.bot.running and not is_shutdown_requested():
            try:
                # Get ready devices (where time has passed for ping or request_task)
                ready_devices = await self._get_ready_devices(devices)
                
                if not ready_devices:
                    # If no ready devices, wait a bit and retry
                    await asyncio.sleep(10)
                    continue
                
                # Process each ready device
                for device in ready_devices:
                    if not self.bot.running or is_shutdown_requested():
                        break
                    
                    try:
                        await self._schedule_device_farming(device)
                    except Exception as e:
                        logger.error(f"Error farming device {device.device_id}: {e}", self.email)
                        continue
                
                # Small delay before next check
                await asyncio.sleep(5)
                    
            except (KeyboardInterrupt, asyncio.CancelledError):
                logger.info("Farming interrupted", self.email)
                break
            except Exception as e:
                error_msg = str(e)
                if "ctype 'void *'" in error_msg or "cdata pointer" in error_msg:
                    logger.error(f"curl_cffi library error detected: {error_msg}", self.email)
                    if not await self.bot._handle_curl_cffi_error():
                        break
                else:
                    logger.error(f"Farming error: {e}", self.email)
                    await asyncio.sleep(10)
        
        await self.bot._cleanup()
        logger.info("Farming process terminated", self.email)
    
    async def _get_ready_devices(self, devices: list) -> list:
        """Get ready devices for farming (where time has passed)"""
        ready_devices = []
        
        for device in devices:
            # If timestamps are not set, device is ready
            if not device.next_ping_at and not device.next_task_request_at:
                ready_devices.append(device)
                continue
            
            # Check if time has passed for ping
            if device.next_ping_at:
                if await verify_sleep(device.next_ping_at):
                    ready_devices.append(device)
                    continue
            
            # Check if time has passed for request_task
            if device.next_task_request_at:
                if await verify_sleep(device.next_task_request_at):
                    ready_devices.append(device)
                    continue
        
        return ready_devices
    
    async def _schedule_device_farming(self, device: Device):
        """Schedule farming for device"""
        if not device:
            return
        
        account = await device.account
        if not account:
            logger.error(f"Device {device.device_id} has no associated account", self.email)
            return
        
        next_task_request_available = True
        if device.next_task_request_at:
            next_task_request_available = await verify_sleep(device.next_task_request_at)
        else:
            next_task_request_available = True
        
        next_ping_available = True
        if device.next_ping_at:
            next_ping_available = await verify_sleep(device.next_ping_at)
        else:
            next_ping_available = True
        
        if not next_task_request_available and not next_ping_available:
            return
        
        try:
            if next_ping_available:
                await self.bot.process_farm(device=device, task='ping', process_id=None)
                next_ping_at = get_sleep_until(minutes=2)
                await device.update_device(next_ping_at=next_ping_at)
            
            if next_task_request_available:
                await self.bot.process_farm(device=device, task='request_task', process_id=None)
                next_task_request_at = get_sleep_until(minutes=1)
                await device.update_device(next_task_request_at=next_task_request_at)
            
        except Exception as error:
            logger.error(f"Error while farming device {device.device_id}: {error}", self.email)

