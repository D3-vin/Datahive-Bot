import asyncio
import random
from typing import Optional, Literal

from app.api.client import DatahiveAPI
from app.core.exceptions import APIError, APIErrorType
from app.core.farm.task import FarmTask
from app.database import get_db
from app.database.models.accounts import Account
from app.database.models.devices import Device
from app.utils.logging import get_logger
from app.utils.proxy import get_proxy_manager
from app.utils.shutdown import is_shutdown_requested
from app.utils.email import EmailValidator, LinkExtractor
from app.config.settings import get_settings

logger = get_logger()


class Bot:
    def __init__(self, email: str, email_password: str, imap_server: str, 
                 proxy: Optional[str] = None, account_index: Optional[int] = None):
        self.email = email
        self.email_password = email_password
        self.imap_server = imap_server
        self.proxy = proxy
        self.account_index = account_index
        self.api = DatahiveAPI(proxy=proxy)
        self.db = get_db()
        self.settings = get_settings()
        self.proxy_manager = get_proxy_manager()
        
        self.running = True
        self.attempt_count = 0

    @staticmethod
    def _build_log_prefix(
        process_id: Optional[int] = None,
        account: Optional[Account] = None,
        device: Optional[Device] = None
    ) -> str:
        """Compose a log prefix omitting process when not set"""
        parts = []
        if process_id is not None:
            parts.append(f'Process: {process_id}')
        if account:
            parts.append(f'{account.email}')
        if device:
            parts.append(f'Device: {device.device_id}')
        return ' | '.join(parts)
    
    async def _get_or_assign_proxy(self) -> Optional[str]:
        """Get proxy from database or assign a new one"""
        account = await Account.get_account(self.email)
        
        if account and account.active_account_proxy:
            self.proxy = account.active_account_proxy
            logger.debug("Using saved proxy from database", self.email)
            return self.proxy
        
        new_proxy = await self.proxy_manager.get_proxy()
        if new_proxy:
            self.proxy = new_proxy
            if account:
                await account.update_proxy(new_proxy)
            logger.debug("Assigned new proxy", self.email)
        
        return self.proxy
    
    async def _rotate_proxy(self) -> Optional[str]:
        """Rotate proxy - get new from pool, release old one"""
        old_proxy = self.proxy
        
        new_proxy = await self.proxy_manager.get_proxy()
        
        if old_proxy:
            await self.proxy_manager.release_proxy(old_proxy)
        
        if new_proxy:
            self.proxy = new_proxy
            
            account = await Account.get_account(self.email)
            if account:
                await account.update_proxy(new_proxy)
            
            logger.info("Rotated proxy", self.email)
        else:
            logger.warning("No proxy available", self.email)
        
        return self.proxy
    
    async def _handle_curl_cffi_error(self) -> bool:
        """Handle curl_cffi errors"""
        logger.info("Handling curl_cffi error: waiting 1-2 seconds before session reset", self.email)
        
        try:
            await asyncio.sleep(1.5)
        except asyncio.CancelledError:
            return False
        
        if not self.running or is_shutdown_requested():
            return False
        
        await self.api.close()
        
        if self.settings.proxy_rotation_enabled:
            try:
                await self._rotate_proxy()
                self.attempt_count = 0
            except Exception as e:
                logger.error(f"Error rotating proxy: {e}", self.email)
        
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            return False
        
        if not self.running or is_shutdown_requested():
            return False
        
        try:
            self.api = DatahiveAPI(proxy=self.proxy)
            logger.debug("New API session created after curl_cffi error", self.email)
            return True
        except Exception as e:
            logger.error(f"Failed to create new API session after curl_cffi error: {e}", self.email)
            return False
    
    async def _prepare_account_proxy(self, value=None) -> Optional[str]:
        """Prepare proxy for account or device"""
        if value:
            if isinstance(value, Device):
                proxy = value.active_device_proxy
                if not proxy:
                    account = await value.account
                    if account and account.active_account_proxy:
                        proxy = account.active_account_proxy
                        await value.update_device_proxy(proxy)
            elif isinstance(value, Account):
                proxy = value.active_account_proxy
            else:
                proxy = None
            
            if not proxy:
                new_proxy = await self.proxy_manager.get_proxy()
                if not new_proxy:
                    raise Exception('No proxies available')
                
                proxy = new_proxy
                self.proxy = new_proxy
                
                if isinstance(value, Device):
                    await value.update_device_proxy(proxy)
                    account = await value.account
                    if account:
                        await account.update_proxy(proxy)
                elif isinstance(value, Account):
                    await value.update_proxy(proxy)
            
            return proxy
        else:
            if self.proxy:
                return self.proxy
            
            return await self._get_or_assign_proxy()
    
    async def _update_account_proxy(
        self,
        account_data,
        attempt: int,
        max_attempts: int,
        proxy: Optional[str] = None,
        process_id: Optional[int] = None
    ):
        """Update proxy for account or device on error"""
        account = None
        if isinstance(account_data, Device):
            account = await account_data.account
        prefix = self._build_log_prefix(process_id, account or None, account_data if isinstance(account_data, Device) else None)
        prefix_text = f'{prefix} | ' if prefix else ''
        
        if not self.settings.proxy_rotation_enabled:
            logger.info(f'{prefix_text}Proxy change disabled | Retrying in {self.settings.retry_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..')
            await asyncio.sleep(self.settings.retry_delay)
            return
        
        proxy_changed_log = f'{prefix_text}Proxy changed | Retrying in {self.settings.retry_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..'
        
        new_proxy = await self._rotate_proxy()
        
        if isinstance(account_data, Device):
            if new_proxy:
                await account_data.update_device_proxy(new_proxy)
        
        logger.info(proxy_changed_log)
        await asyncio.sleep(self.settings.retry_delay)
    
    async def _validate_email(self, proxy: Optional[str] = None) -> dict:
        """Validate email via IMAP"""
        try:
            validator = EmailValidator(
                self.imap_server,
                self.email,
                self.email_password
            )
            result = await validator.validate(proxy=proxy)
            return result
        except Exception as e:
            logger.error(f"Error in _validate_email for {self.email}: {e}", self.email)
            return {
                'status': False,
                'identifier': self.email,
                'data': None,
                'error': f'Validation failed: {str(e)}'
            }
    
    async def _extract_link(self, proxy: Optional[str] = None) -> dict:
        """Extract confirmation link from email"""
        try:
            extractor = LinkExtractor(
                imap_server=self.imap_server,
                email=self.email,
                password=self.email_password
            )
            result = await extractor.extract_link(proxy=proxy)
            return result
        except Exception as e:
            logger.error(f"Error in _extract_link for {self.email}: {e}", self.email)
            return {
                'status': False,
                'identifier': self.email,
                'data': None,
                'error': f'Extraction failed: {str(e)}'
            }
    
    async def _get_auth_token(self) -> Optional[str]:
        """Get auth_token from database"""
        try:
            await self.db.init()
            token = await Account.get_auth_token(self.email)
            if token:
                self.api.auth_token = token
            return token
        except Exception as e:
            logger.error(f"Failed to get auth token: {e}", self.email)
            return None
    
    async def _cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if hasattr(self, 'api') and self.api:
                await self.api.close()
            
            if hasattr(self, 'proxy') and self.proxy:
                try:
                    await self.proxy_manager.release_proxy(self.proxy)
                except Exception:
                    pass
                    
        except (asyncio.CancelledError, Exception) as e:
            if isinstance(e, asyncio.CancelledError):
                if hasattr(self, 'api') and self.api:
                    try:
                        await self.api.close()
                    except Exception:
                        pass
            else:
                logger.debug(f"Cleanup error (safe to ignore): {e}", self.email)
    
    async def process_task(self, device: Device, account: Account, api: DatahiveAPI, process_id: Optional[int] = None):
        """Process farming task"""
        task_data = await api.request_task(device=device)
        prefix = self._build_log_prefix(process_id, account, device)
        prefix_text = f'{prefix} | ' if prefix else ''
        
        if task_data:
            logger.info(f'{prefix_text}Received task, processing')
            task_id = task_data.get('id')
            yaml_rules = task_data.get('ruleCollection').get('yamlRules')
            target_url = task_data.get('vars').get('url')
            request_timeout = task_data.get('vars').get('timeout')
            
            target_page_html = await api.fetch_task_html(target_url, timeout=request_timeout)
            
            farm_task = FarmTask(
                task_id=task_id,
                target_url_html=target_page_html,
                task_yaml_rules=yaml_rules,
                task_vars=task_data.get('vars')
            )
            task_json_data = farm_task.build_task_json_data()
            
            await asyncio.sleep(random.randint(2, 5))
            
            if task_json_data.get('result').get('pageData').get('fields').get('title') == '':
                logger.info(f'{prefix_text}Page data not extracted, submitting empty result')
            else:
                logger.info(f'{prefix_text}Page data extracted, completing task')
            
            await api.complete_task(device=device, task_id=task_id, json_data=task_json_data)
            logger.success(f'{prefix_text}Task completed')
        else:
            logger.info(f'{prefix_text}No task available')

    async def process_farm(
        self,
        device: Device,
        task: Literal['ping', 'request_task'],
        process_id: Optional[int] = None
    ):
        """Process account farming"""
        max_attempts = self.settings.max_farm_attempts
        account = await device.account
        api = None
        prefix = self._build_log_prefix(process_id, account, device)
        prefix_text = f'{prefix} | ' if prefix else ''
        
        for attempt in range(max_attempts):
            try:
                proxy = await self._prepare_account_proxy(device)
                api = DatahiveAPI(proxy=proxy, auth_token=account.auth_token)
                
                if task == 'ping':
                    logger.info(f'{prefix_text}Sending ping')
                    await api.send_ping(device=device)
                    logger.success(f'{prefix_text}Ping sent')
                else:
                    logger.info(f'{prefix_text}Requesting task')
                    await self.process_task(device=device, account=account, api=api, process_id=process_id)
                
                if api:
                    await api.close()
                return
                
            except APIError as error:
                if hasattr(error, 'error_type') and error.error_type == APIErrorType.CLIENT_UPGRADE_REQUIRED:
                    logger.warning(f'{prefix_text}Waiting for synchronization | Skipped until next cycle')
                    if api:
                        await api.close()
                    return
                
                logger.error(f'{prefix_text}Error occurred during farming (APIError): {error} | Skipped until next cycle')
                if api:
                    await api.close()
                return
            except Exception as error:
                error_str = str(error)
                if 'Proxy Authentication Required' in error_str and not self.settings.proxy_rotation_enabled:
                    logger.error(f'{prefix_text}Proxy authentication failed, please check your proxy settings and restart the bot | Skipped until next cycle')
                    if api:
                        await api.close()
                    return
                
                is_last_attempt = attempt == max_attempts - 1
                if is_last_attempt:
                    logger.error(f'{prefix_text}Max attempts reached, unable to farm | Skipped until next cycle | Last error: {str(error)}')
                    if api:
                        await api.close()
                    return
                
                logger.error(f'{prefix_text}Error occurred during farming (Generic Exception): {error}')
                await self._update_account_proxy(
                    device,
                    attempt,
                    max_attempts,
                    proxy=api.proxy if api else None,
                    process_id=process_id
                )
                if api:
                    await api.close()
                continue
        
        if api:
            await api.close()
    
    def stop(self) -> None:
        """Stop bot"""
        self.running = False
