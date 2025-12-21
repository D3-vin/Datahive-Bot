import asyncio
from typing import Optional

from app.core.base import Bot
from app.core.exceptions import APIError
from app.api.client import DatahiveAPI
from app.utils.logging import get_logger
from app.utils.results import get_results_manager
from app.utils.email import EmailValidator, LinkExtractor
from app.database.models.accounts import Account

logger = get_logger()


class RegistrationModule:
    def __init__(self, email: str, email_password: str, imap_server: str, bot: Bot):
        self.email = email
        self.email_password = email_password
        self.imap_server = imap_server
        self.bot = bot
        self.results_manager = get_results_manager()
    
    async def process(self) -> bool:
        """Main registration method"""
        max_attempts = self.bot.settings.max_registration_attempts
        api = None
        
        for attempt in range(max_attempts):
            try:
                await self.bot.db.init()
                
                existing_account = await Account.get_account(self.email)
                if existing_account and existing_account.auth_token:
                    logger.info("Account already registered, skipping", self.email)
                    if api:
                        await api.close()
                    return True
                
                logger.info(f"Starting registration (attempt {attempt + 1}/{max_attempts})", self.email)
                
                if await self._attempt_registration():
                    logger.success("Registration completed successfully", self.email)
                    await self.results_manager.save_registration_result(self.email, self.email_password, True)
                    if api:
                        await api.close()
                    return True
                
            except APIError as error:
                logger.error(f"Registration failed (APIError): {error}", self.email)
                if api:
                    await api.close()
                await self.results_manager.save_registration_result(self.email, False)
                return False
            except Exception as error:
                error_str = str(error)
                
                # Check if this is the last attempt
                is_last_attempt = attempt == max_attempts - 1
                if is_last_attempt:
                    logger.error(f"Registration failed after {max_attempts} attempts. Last error: {str(error)}", self.email)
                    if api:
                        await api.close()
                    await self.results_manager.save_registration_result(self.email, self.email_password, False)
                    return False
                    
                # Handle curl_cffi errors separately
                if "ctype 'void *'" in error_str or "cdata pointer" in error_str:
                    logger.error(f"curl_cffi library error detected: {error_str}", self.email)
                    if api:
                        await api.close()
                    if not await self.bot._handle_curl_cffi_error():
                        return False
                    continue
                
                logger.error(f"Registration failed (attempt {attempt + 1}/{max_attempts}): {error}", self.email)
                await self._update_proxy_and_retry(attempt, max_attempts, api, error=error)
                api = None  # API already closed in _update_proxy_and_retry
        
        logger.error(f"Registration failed after {max_attempts} attempts", self.email)
        await self.results_manager.save_registration_result(self.email, self.email_password, False)
        return False
    
    async def _attempt_registration(self) -> bool:
        """Attempt registration"""
        try:
            # 1. Email validation via IMAP
            logger.info("Validating email...", self.email)
            # Check use_proxy_for_imap setting
            imap_proxy = self.bot.proxy if self.bot.settings.use_proxy_for_imap else None
            validation_result = await self._validate_email(imap_proxy)
            if not validation_result.get('status'):
                logger.error(f"Email validation failed: {validation_result.get('error')}", self.email)
                return False
            
            # 2. Send OTP code
            logger.info("Sending email confirmation request...", self.email)
            await self.bot.api.send_otp(self.email)
            
            # 3. Extract verification link from email
            logger.info("Confirmation email sent, extracting confirmation code...", self.email)
            confirm_code = await self._extract_verification_link(imap_proxy)
            
            if not confirm_code.get('status'):
                logger.error(f"Confirmation code not found: {confirm_code.get('data')}", self.email)
                return False
            
            # 4. Verify URL and get Supabase token
            confirm_url = confirm_code.get('data').replace('amp;', '')
            logger.success("Confirmation code extracted, verifying account...", self.email)
            
            supabase_token = await self.bot.api.verify_url(confirm_url)
            logger.debug(f"Supabase token obtained: {supabase_token[:50]}...", self.email)
            
            # 5. Login with token
            auth_response = await self.bot.api.login(supabase_token)
            logger.debug(f"Auth response received", self.email)
            
            auth_token = auth_response['token']
            is_sign_up_required = auth_response['isSignupRequired']
            self.bot.api.auth_token = auth_token
            
            # 6. Complete registration (if required)
            if is_sign_up_required:
                invite_code = await self._get_ref_code()
                # Check that code is valid (not empty and not test value)
                if invite_code and invite_code.strip() and invite_code.lower() != "invite_code":
                    logger.info(f"Completing sign up with referral code: {invite_code}", self.email)
                    await self.bot.api.complete_sign_up(invite_code)
                else:
                    logger.warning("No valid referral code available, completing sign up without code", self.email)
                    await self.bot.api.complete_sign_up(None)
            
            # 7. Get user information
            user_info = await self.bot.api.request_user()
            user_id = user_info.get('id')
            
            # 8. Get referral code
            referral_code = await self.bot.api.get_referral_code()
            
            # 9. Save to database
            account = await Account.create_account(
                email=self.email,
                email_password=self.email_password,
                auth_token=auth_token,
                user_id=user_id,
                invite_code=referral_code,
                imap_server=self.imap_server
            )
            
            if self.bot.proxy and account:
                await account.update_proxy(self.bot.proxy)
            
            logger.success("Account registered and saved to database", self.email)
            return True
            
        except APIError as error:
            logger.error(f"Registration failed (APIError): {error}", self.email)
            return False
        except Exception as e:
            logger.error(f"Registration attempt failed: {e}", self.email)
            return False
        finally:
            await self.bot.api.close()
    
    async def _validate_email(self, proxy: Optional[str] = None) -> dict:
        """Validate email via IMAP"""
        validator = EmailValidator(
            self.imap_server,
            self.email,
            self.email_password
        )
        return await validator.validate(proxy=proxy)
    
    async def _extract_verification_link(self, proxy: Optional[str] = None) -> dict:
        """Extract verification link from email"""
        extractor = LinkExtractor(
            imap_server=self.imap_server,
            email=self.email,
            password=self.email_password
        )
        return await extractor.extract_link(proxy=proxy)
    
    async def _get_ref_code(self) -> Optional[str]:
        """Get referral code"""
        settings = self.bot.settings
        
        if settings.use_random_ref_code_from_db:
            invite_code = await Account.get_random_invite_code()
            if invite_code:
                logger.info(f"Using random referral code from database: {invite_code}", self.email)
                return invite_code
            else:
                logger.info("No referral codes available in database, completing sign up without code", self.email)
                return None
        else:
            static_code = settings.static_referral_code
            if static_code:
                logger.info(f"Using static referral code from config: {static_code}", self.email)
                return static_code
            else:
                logger.info("No static referral code specified, completing sign up without code", self.email)
                return None
    
    async def _update_proxy_and_retry(self, attempt: int, max_attempts: int, api=None, error: Exception = None):
        """Update proxy and delay before retry"""
        from app.config.settings import get_settings
        
        settings = get_settings()
        error_delay = settings.retry_delay
        
        should_rotate_proxy = True
        if error:
            should_rotate_proxy = self._should_rotate_proxy_for_error(error)
        
        if not settings.proxy_rotation_enabled:
            logger.info(f"Proxy change disabled. Retrying in {error_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..", self.email)
            await asyncio.sleep(error_delay)
            return
        
        if should_rotate_proxy:
            try:
                if self.bot.proxy:
                    await self.bot.proxy_manager.release_proxy(self.bot.proxy)
                
                new_proxy = await self.bot.proxy_manager.get_proxy()
                
                if new_proxy and new_proxy != self.bot.proxy:
                    self.bot.proxy = new_proxy
                    logger.info(f"Proxy changed. Retrying in {error_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..", self.email)
                else:
                    logger.info(f"No alternative proxy available. Retrying in {error_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..", self.email)
            except Exception as e:
                logger.warning(f"Error rotating proxy: {e}. Retrying in {error_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..", self.email)
        else:
            logger.info(f"Error is not proxy-related. Retrying in {error_delay}s.. | Attempt: {attempt + 1}/{max_attempts}..", self.email)
        
        if api:
            try:
                await api.close()
            except:
                pass
        
        self.bot.api = DatahiveAPI(proxy=self.bot.proxy)
        await asyncio.sleep(error_delay)
    
    def _should_rotate_proxy_for_error(self, error: Exception = None) -> bool:
        """Determine if proxy should be rotated for this error"""
        if error is None:
            return True
        
        error_msg = str(error).lower()
        
        database_errors = [
            'table',
            'column',
            'database',
            'sqlite',
            'no such table',
            'no such column',
            'schema',
            'migration'
        ]
        
        non_proxy_errors = [
            'alias not found',
            'email already exist',
            'invalid credentials',
            'unauthorized',
            'forbidden',
            'not found',
            'bad request',
            'validation failed',
            'session is closed',
            'session closed',
            'cannot send request'
        ]
        
        if any(pattern in error_msg for pattern in database_errors + non_proxy_errors):
            return False
        
        proxy_errors = [
            'connection',
            'connect',
            'timeout',
            'timed out',
            'network',
            'unreachable',
            'refused',
            'reset',
            'curl',
            'ssl',
            'tls',
            'tunnel',
            'failed to connect',
            'connection aborted',
            'connection reset',
            'connection refused',
            'could not connect',
            'dns',
            'proxy',
            'curl_cffi',
            'ctype',
            'cdata pointer',
            'requesterror',
            'curlerror'
        ]
        
        error_type = type(error).__name__.lower()
        if 'requesterror' in error_type or 'curlerror' in error_type:
            return True
        
        if any(pattern in error_msg for pattern in proxy_errors):
            return True
        
        return False
