import asyncio
import random
import uuid
from typing import Optional

from app.core.base import Bot
from app.database.models.accounts import Account
from app.database.models.devices import Device
from app.models.device_fingerprints import DESKTOP_USER_AGENTS, CPU_FINGERPRINTS
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
            logger.info("No devices found for account. Creating devices...", self.email)
            devices = await self._create_devices_for_account(account)
            if not devices:
                logger.error("Failed to create devices for account", self.email)
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
    
    async def _create_devices_for_account(self, account: Account) -> list:
        """Create devices for account if none exist"""
        device_settings = self.bot.settings.device_settings.get('active_devices_per_account', {})
        devices_per_account_min = device_settings.get('min', 1)
        devices_per_account_max = device_settings.get('max', 1)
        devices_count = random.randint(devices_per_account_min, devices_per_account_max)
        
        # Get proxies for devices
        proxies = []
        for _ in range(devices_count):
            proxy = await self.bot.proxy_manager.get_proxy()
            if proxy:
                proxies.append(proxy)
        
        if not proxies:
            logger.warning("No proxies available for device creation", self.email)
            return []
        
        # Create devices
        created_devices = []
        user_agents = random.choices(DESKTOP_USER_AGENTS, k=len(proxies))
        cpu_fingerprints = random.choices(CPU_FINGERPRINTS, k=len(proxies))
        cpu_architecture = 'x86_64'
        
        for proxy, user_agent, cpu_fingerprint in zip(proxies, user_agents, cpu_fingerprints):
            try:
                browser_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, proxy))
                device = await Device.create_device_for_account(
                    account=account,
                    user_agent=user_agent,
                    cpu_architecture=cpu_architecture,
                    cpu_model=cpu_fingerprint[0],
                    cpu_processor_count=int(cpu_fingerprint[1]),
                    device_os=cpu_fingerprint[2],
                    device_id=browser_id,
                    active_device_proxy=proxy
                )
                created_devices.append(device)
            except Exception as e:
                logger.debug(f"Device creation skipped: {e}", self.email)
        
        if created_devices:
            logger.info(f"Created {len(created_devices)} device(s) for account", self.email)
        
        return created_devices

