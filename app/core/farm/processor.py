"""
Farm processor for multiprocess farming
"""

import asyncio
import os
import platform
import random
import sys
import uuid
from typing import List, Dict, Set, Optional
import psutil

# Bot import is inside schedule_device_farming to avoid circular import
from app.database.models.accounts import Account
from app.database.models.devices import Device
from app.models.device_fingerprints import DESKTOP_USER_AGENTS, CPU_FINGERPRINTS
from app.utils.logging import get_logger
from app.utils.sleep import get_sleep_until, verify_sleep
from app.utils.proxy import get_proxy_manager
from app.config.settings import get_settings

logger = get_logger()

proxies_lock = asyncio.Lock()


class FarmProcessor:
    """Farm processor for account farming"""
    
    def __init__(self, process_id: int, accounts: List[dict]):
        self.process_id = process_id
        self.accounts = accounts
        self.settings = get_settings()
        self.proxy_manager = get_proxy_manager()
        self.total_accounts = len(accounts)
    
    @staticmethod
    def _batched(seq, n):
        """Split sequence into batches"""
        for i in range(0, len(seq), n):
            yield seq[i:i + n]
    
    async def get_accounts(self, accounts: List[dict], batch_size: int = 2000) -> List[Account]:
        """Get accounts from database"""
        logger.debug(f'Process: {self.process_id} | Preparing {len(accounts)} accounts...')
        if not accounts:
            logger.warning(f'Process: {self.process_id} | No accounts provided for farming.')
            return []
        
        db_accounts = []
        emails = [a['email'] for a in accounts if a.get('email')]
        
        for chunk in FarmProcessor._batched(emails, batch_size):
            if not chunk:
                continue
            rows = await Account.filter(email__in=chunk).all()
            db_accounts.extend(rows)
        
        if not db_accounts:
            logger.warning(f'Process: {self.process_id} | No matching accounts found in DB.')
            return []
        
        return db_accounts
    
    async def _prepare_accounts(self, accounts: List[dict]) -> List[Account]:
        """Prepare accounts for farming"""
        prepared_accounts = await self.get_accounts(accounts)
        
        for account in prepared_accounts:
            if not account.auth_token:
                logger.warning(
                    f'Process: {self.process_id} | Account: {account.email} | Account not logged in. Skipped for farming.'
                )
                prepared_accounts.remove(account)
        
        if not prepared_accounts:
            logger.warning(
                f'Process: {self.process_id} | No accounts prepared for farming. Most likely, accounts not logged in.'
            )
            return []
        
        logger.debug(
            f'Process: {self.process_id} | Prepared {len(prepared_accounts)}/{len(accounts)} accounts.'
        )
        return prepared_accounts
    
    async def _get_proxies(self, count: int) -> List[str]:
        """Get proxies from manager"""
        proxies = []
        for i in range(count):
            proxy = await self.proxy_manager.get_proxy()
            if proxy:
                proxies.append(proxy)
        return proxies
    
    async def _create_devices_for_account(self, account: Account, limit: int) -> List[Device]:
        """Create devices for account"""
        nodes = await Device.get_devices_with_limit(account, limit)
        if not nodes or len(nodes) < limit:
            nodes_to_create = limit - len(nodes) if nodes else limit
            proxies = await self._get_proxies(nodes_to_create)
        
            if len(proxies) < nodes_to_create:
                logger.warning(
                    f'Process: {self.process_id} | Account: {account.email} | '
                    f'Not enough proxies available ({len(proxies)}/{nodes_to_create}). Creating devices with available proxies.'
                )
                nodes_to_create = len(proxies)
            
            if nodes_to_create > 0:
                user_agents = random.choices(DESKTOP_USER_AGENTS, k=nodes_to_create)
                cpu_fingerprints = random.choices(CPU_FINGERPRINTS, k=nodes_to_create)
                cpu_architecture = 'x86_64'
                browser_ids = [str(uuid.uuid3(uuid.NAMESPACE_DNS, proxy)) for proxy in proxies]
                
                for browser_id, user_agent, proxy, cpu_fingerprint in zip(
                    browser_ids, user_agents, proxies, cpu_fingerprints
                ):
                    try:
                        await Device.create_device_for_account(
                            account=account,
                            user_agent=user_agent,
                            cpu_architecture=cpu_architecture,
                            cpu_model=cpu_fingerprint[0],
                            cpu_processor_count=int(cpu_fingerprint[1]),
                            device_os=cpu_fingerprint[2],
                            device_id=browser_id,
                            active_device_proxy=proxy
                        )
                    except Exception as e:
                        logger.debug(f'Process: {self.process_id} | Account: {account.email} | Device creation skipped: {e}')
                        pass
        
        nodes = await Device.get_devices_with_limit(account, limit)
        return nodes
    
    async def set_delay_for_devices(self, devices: List[Device], batch_size: int = 1000):
        """Set delay for devices"""
        if not devices:
            return
        
        delay_min = self.settings.delay_min
        delay_max = self.settings.delay_max
        
        if delay_max <= 0 or delay_min < 0:
            return
        
        for device in devices:
            delay = random.randint(delay_min, delay_max)
            device.next_ping_at = get_sleep_until(seconds=delay)
            device.next_task_request_at = get_sleep_until(seconds=delay)
        
        for chunk in self._batched(devices, batch_size):
            await Device.bulk_update_devices(chunk, ['next_ping_at', 'next_task_request_at'])
    
    async def _prepare_devices(self, accounts: List[Account]) -> List[Device]:
        """Prepare devices for farming"""
        logger.debug(f'Process: {self.process_id} | Preparing devices for {len(accounts)} accounts...')
        tasks = []
        
        devices_per_account_min = self.settings.device_settings.get('active_devices_per_account', {}).get('min', 1)
        devices_per_account_max = self.settings.device_settings.get('active_devices_per_account', {}).get('max', 1)
        
        for account in accounts:
            devices_per_account = random.randint(devices_per_account_min, devices_per_account_max)
            tasks.append(self._create_devices_for_account(account, devices_per_account))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        filtered_results = []
        errors = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(result)
            elif isinstance(result, list):
                filtered_results.extend(result)
        
        if errors:
            logger.warning(f'Process: {self.process_id} | Errors (related to database): {errors}')
        
        if not filtered_results:
            logger.warning(f'Process: {self.process_id} | No devices prepared for farming.')
            return []
        
        await self.set_delay_for_devices(filtered_results)
        logger.debug(f'Process: {self.process_id} | Prepared {len(filtered_results)} devices for farming.')
        return filtered_results
    
    @staticmethod
    async def _get_ready_devices(prepared_devices: List[Device], process_id: int, limit: int = 200) -> List[Device]:
        """Get ready devices for farming"""
        ready_devices = []
        for device in prepared_devices:
            if not device.next_ping_at and not device.next_task_request_at:
                ready_devices.append(device)
                continue
            
            if device.next_ping_at:
                if await verify_sleep(device.next_ping_at):
                    ready_devices.append(device)
                    continue
            
            if device.next_task_request_at:
                if await verify_sleep(device.next_task_request_at):
                    ready_devices.append(device)
                    continue
            
            if len(ready_devices) >= limit:
                break
            
        return ready_devices[:limit]
    
    @staticmethod
    async def schedule_device_farming(device: Device, process_id: int):
        """Schedule farming for device"""
        if not device or not isinstance(device, Device):
            return
        
        account = None
        try:
            account = await device.account
        except Exception:
            pass
        
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
            from app.core.base import Bot
            
            bot = Bot(
                email=account.email,
                email_password=account.email_password or '',
                imap_server=account.imap_server or '',
                proxy=None,
                account_index=None
            )
            
            if next_ping_available:
                await bot.process_farm(device=device, task='ping', process_id=process_id)
                next_ping_at = get_sleep_until(minutes=2)
                await device.update_device(next_ping_at=next_ping_at)
            
            if next_task_request_available:
                await bot.process_farm(device=device, task='request_task', process_id=process_id)
                next_task_request_at = get_sleep_until(minutes=1)
                await device.update_device(next_task_request_at=next_task_request_at)
            
            await bot._cleanup()
            return None
        except Exception as error:
            if account:
                logger.error(f'Process: {process_id} | Account: {account.email} | Unknown error while farming: {error}')
            else:
                logger.error(f'Process: {process_id} | Unknown error while farming with invalid account: {error}')
            return None
    
    async def _run_device_farming(
        self,
        device: Device,
        device_task_timeout: int,
        semaphore: asyncio.Semaphore,
        devices_in_progress: Set[str]
    ):
        """Run farming for device"""
        try:
            async with semaphore:
                try:
                    await asyncio.wait_for(
                        self.schedule_device_farming(device, self.process_id),
                        timeout=device_task_timeout
                    )
                except asyncio.TimeoutError:
                    try:
                        account = await device.account
                        logger.error(
                            f'Process: {self.process_id} | Account: {account.email} | Device: {device.device_id} | '
                            f'Farming task timed out ({device_task_timeout}s)'
                        )
                    except Exception:
                        logger.error(
                            f'Process: {self.process_id} | Device: {device.device_id} | '
                            f'Farming task timed out ({device_task_timeout}s), account fetch failed'
                        )
        except Exception as error:
            try:
                account = await device.account
                logger.error(
                    f'Process: {self.process_id} | Account: {account.email} | Device: {device.device_id} | '
                    f'Error in device task: {error}'
                )
            except Exception:
                logger.error(
                    f'Process: {self.process_id} | Device: {device.device_id} | '
                    f'Error in device task (account fetch failed): {error}'
                )
        finally:
            devices_in_progress.discard(device.device_id)
    
    async def farm_continuously(self) -> Optional[str]:
        """Continuously farm accounts"""
        prepared_accounts = await self._prepare_accounts(self.accounts)
        if not prepared_accounts:
            return None
        
        prepared_devices = await self._prepare_devices(prepared_accounts)
        if not prepared_devices:
            return None
        
        logger.debug(f'Process: {self.process_id} | DB-driven farming started')
        
        max_devices_per_batch = self.settings.farm_settings.get('max_devices_per_batch', 200)
        max_concurrent_tasks = self.settings.farm_settings.get('max_concurrent_tasks', 200)
        device_task_timeout = self.settings.farm_settings.get('device_task_timeout', 60)
        semaphore = asyncio.Semaphore(max_concurrent_tasks)
        devices_in_progress = set()
        
        try:
            while True:
                ready_devices = await self._get_ready_devices(
                    prepared_devices=prepared_devices,
                    process_id=self.process_id,
                    limit=max_devices_per_batch
                )
                ready_devices = [d for d in ready_devices if d.device_id not in devices_in_progress]
                
                if not ready_devices:
                    await asyncio.sleep(5)
                    continue
                
                for device in ready_devices:
                    devices_in_progress.add(device.device_id)
                    asyncio.create_task(
                        self._run_device_farming(
                            device=device,
                            device_task_timeout=device_task_timeout,
                            semaphore=semaphore,
                            devices_in_progress=devices_in_progress
                        )
                    )
                
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info(f'Process: {self.process_id} | Farming loop cancelled, shutting down...')
            return None
        except Exception as error:
            logger.error(f'Process: {self.process_id} | Fatal error in farming loop: {error}')
            return None
    
    async def run(self) -> None:
        """Start farming"""
        try:
            await self.farm_continuously()
        except Exception as e:
            logger.error(f"Process {self.process_id}: Farming error: {e}")
