from typing import Optional, Union

from aiohttp import ClientSession, ClientTimeout
from aiohttp_socks import ProxyConnector

from app.core.base import Bot
from app.utils.logging import get_logger

from Jam_Twitter_API.account_sync import TwitterAccountSync
from Jam_Twitter_API.errors import TwitterAccountSuspended, TwitterError, IncorrectData, RateLimitError

logger = get_logger()


class TwitterBindingModule:
    def __init__(self, email: str, twitter_tokens: list, bot: Bot):
        self.email = email
        self.twitter_tokens = twitter_tokens
        self.bot = bot
        self.current_token_index = 0
    
    @property
    def current_twitter_token(self) -> Optional[str]:
        if self.current_token_index < len(self.twitter_tokens):
            return self.twitter_tokens[self.current_token_index]
        return None
    
    def try_next_token(self) -> bool:
        self.current_token_index += 1
        return self.current_token_index < len(self.twitter_tokens)
    
    async def process(self) -> bool:
        await self.bot.db.init()
        
        while self.current_token_index < len(self.twitter_tokens):
            current_token = self.current_twitter_token
            if not current_token:
                break
            
            logger.info(f"Trying Twitter token {self.current_token_index + 1}/{len(self.twitter_tokens)}", self.bot.email)
            
            try:
                binding_result = await self._attempt_twitter_binding()
                
                if binding_result is True:
                    logger.success("Twitter binding completed successfully", self.bot.email)
                    return True
                elif binding_result == "already_linked":
                    logger.warning(f"Token {self.current_token_index + 1} already linked, trying next token", self.bot.email)
                    if not self.try_next_token():
                        logger.error("All Twitter tokens already linked", self.bot.email)
                        return False
                    continue
                else:
                    logger.warning(f"Token {self.current_token_index + 1} failed, trying next token", self.bot.email)
                    if not self.try_next_token():
                        break
                    continue
                    
            except Exception as e:
                logger.error(f"Twitter binding failed: {e}", self.bot.email)
                if not self.try_next_token():
                    break
                continue
        
        logger.error("No available Twitter tokens for binding", self.bot.email)
        return False
    
    async def _attempt_twitter_binding(self) -> Union[bool, str]:
        try:
            oauth_url = await self._get_datahive_oauth_url()
            if not oauth_url:
                return False
            
            oauth_params = self._parse_oauth_url(oauth_url)
            if not oauth_params:
                logger.error("Failed to parse OAuth URL parameters", self.bot.email)
                return False
            
            proxy_str = self.bot.proxy if self.bot.proxy else ""
            
            current_token = self.current_twitter_token
            if not current_token:
                logger.error("No more Twitter tokens available", self.bot.email)
                return False
            
            account = TwitterAccountSync.run(
                auth_token=current_token, 
                proxy=proxy_str, 
                setup_session=True
            )
            
            bind_result = account.bind_account_v2(oauth_params)
            
            if bind_result:
                logger.debug(f"Got OAuth code: {bind_result}", self.bot.email)
                
                callback_success = await self._complete_oauth_callback(bind_result, oauth_params["state"])
                
                if callback_success is True:
                    logger.success("Twitter account bound successfully", self.bot.email)
                    return True
                elif callback_success == "already_linked":
                    return "already_linked"
                else:
                    logger.debug("Failed to complete OAuth callback", self.bot.email)
                    return False
            else:
                logger.error("Failed to bind Twitter account", self.bot.email)
                return False
                
        except TwitterAccountSuspended as error:
            logger.error(f"Twitter account suspended: {error}", self.bot.email)
            return False
        except TwitterError as error:
            error_msg = getattr(error, 'error_message', str(error))
            error_code = getattr(error, 'error_code', 'unknown')
            logger.error(f"Twitter error: {error_msg} | {error_code}", self.bot.email)
            return False
        except IncorrectData as error:
            logger.error(f"Incorrect data: {error}", self.bot.email)
            return False
        except RateLimitError as error:
            logger.error(f"Rate limit exceeded: {error}", self.bot.email)
            return False
        except Exception as e:
            logger.error(f"Twitter binding attempt failed: {e}", self.bot.email)
            return False
    
    async def _complete_oauth_callback(self, code: str, state: str) -> Union[bool, str]:
        try:
            callback_url = f"https://api.datahive.ai/api/service/oauth2/callback?state={state}&code={code}"
            
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors", 
                "Sec-Fetch-Site": "same-site",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            }
            
            connector = ProxyConnector.from_url(self.bot.proxy) if self.bot.proxy else None
            
            async with ClientSession(connector=connector, timeout=ClientTimeout(total=30)) as session:
                async with session.get(callback_url, headers=headers, ssl=False, allow_redirects=False) as response:
                    
                    if response.status == 302:
                        redirect_location = response.headers.get('Location', '')
                        logger.debug(f"Redirect location: {redirect_location}", self.bot.email)
                        
                        if "twitter-connect.openlayer.tech/?success=" in redirect_location:
                            if "referralCode=" in redirect_location:
                                referral_code = redirect_location.split("referralCode=")[1]
                                logger.success(f"Twitter binding successful! Referral code: {referral_code}", self.bot.email)
                            else:
                                logger.success("Twitter binding successful!", self.bot.email)
                            return True
                        
                        elif "twitter-connect.openlayer.tech/?error=" in redirect_location:
                            error_msg = redirect_location.split("error=")[1].replace("+", " ")
                            
                            if "already+been+linked" in redirect_location or "already been linked" in error_msg:
                                logger.warning(f"Twitter account already linked: {error_msg}", self.bot.email)
                                return "already_linked"
                            else:
                                logger.error(f"Twitter binding failed: {error_msg}", self.bot.email)
                                return False
                        
                        else:
                            logger.debug(f"Unknown redirect location: {redirect_location}", self.bot.email)
                            return False
                    
                    elif response.status == 200:
                        try:
                            result = await response.json()
                            if result.get("success"):
                                logger.success("OAuth callback completed successfully (direct response)", self.bot.email)
                                return True
                            else:
                                logger.error(f"OAuth callback failed: {result.get('msg', 'Unknown error')}", self.bot.email)
                                return False
                        except Exception:
                            logger.success("OAuth callback completed (non-JSON response)", self.bot.email)
                            return True
                    
                    else:
                        logger.error(f"OAuth callback failed with status {response.status}", self.bot.email)
                        return False
                        
        except Exception as e:
            logger.error(f"Error completing OAuth callback: {e}", self.bot.email)
            return False
    
    async def _get_datahive_oauth_url(self) -> Optional[str]:
        try:
            auth_token = await self.bot._get_auth_token()
            if not auth_token:
                logger.error("Failed to get auth token", self.bot.email)
                return None
            
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Authorization": f"Bearer {auth_token}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors", 
                "Sec-Fetch-Site": "same-site",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            }
            
            connector = None
            if self.bot.proxy:
                try:
                    connector = ProxyConnector.from_url(self.bot.proxy)
                except Exception as e:
                    logger.error(f"Failed to create proxy connector: {e}", self.bot.email)
                    return None
            
            async with ClientSession(connector=connector, timeout=ClientTimeout(total=30)) as session:
                try:
                    async with session.get("https://api.datahive.ai/api/service/oauth2/twitter?", headers=headers, ssl=False) as response:
                        if response.status == 200:
                            result = await response.json()
                            if result.get("success") and result.get("data", {}).get("url"):
                                oauth_url = result["data"]["url"]
                                logger.debug("Retrieved OAuth URL from Datahive backend", self.bot.email)
                                return oauth_url
                            else:
                                logger.error(f"Invalid response from Datahive: {result}", self.bot.email)
                                return None
                        elif response.status == 401:
                            logger.error("Unauthorized (401) - token may be invalid or expired", self.bot.email)
                            return None
                        else:
                            text = await response.text()
                            logger.error(f"Failed to get OAuth URL, status: {response.status}, response: {text[:200]}", self.bot.email)
                            return None
                except Exception as e:
                    logger.error(f"Request error getting OAuth URL: {e}", self.bot.email)
                    return None
                        
        except Exception as e:
            logger.error(f"Error getting OAuth URL from Datahive: {e}", self.bot.email)
            return None
    
    def _parse_oauth_url(self, oauth_url: str) -> Optional[dict]:
        try:
            from urllib.parse import urlparse, parse_qs
            
            parsed = urlparse(oauth_url)
            params = parse_qs(parsed.query)
            
            oauth_params = {}
            
            param_mapping = {
                'response_type': 'response_type',
                'client_id': 'client_id', 
                'redirect_uri': 'redirect_uri',
                'state': 'state',
                'code_challenge': 'code_challenge',
                'code_challenge_method': 'code_challenge_method',
                'scope': 'scope'
            }
            
            for url_param, oauth_param in param_mapping.items():
                if url_param in params and len(params[url_param]) > 0:
                    oauth_params[oauth_param] = params[url_param][0]
            
            required_params = ['response_type', 'client_id', 'redirect_uri', 'scope', 'state']
            for param in required_params:
                if param not in oauth_params:
                    logger.error(f"Missing required OAuth parameter: {param}", self.bot.email)
                    return None
            
            logger.debug("Successfully parsed OAuth parameters from Datahive URL", self.bot.email)
            return oauth_params
            
        except Exception as e:
            logger.error(f"Error parsing OAuth URL: {e}", self.bot.email)
            return None

