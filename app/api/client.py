from functools import wraps
from typing import Optional

from app.api.base import BaseAPIClient
from app.core.exceptions import APIError
from app.database.models.devices import Device
from app.utils.logging import get_logger

logger = get_logger()


def require_auth_token(func):
    """Decorator to check for auth_token presence"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.auth_token:
            raise APIError('Auth token is required.')
        return await func(self, *args, **kwargs)
    return wrapper


class DatahiveAPI(BaseAPIClient):
    """API client for Datahive"""
    
    def __init__(self, proxy: Optional[str] = None, auth_token: Optional[str] = None):
        super().__init__(api_url=None, proxy=proxy)
        self.auth_token = auth_token

    async def send_otp(self, email: str):
        """Send OTP code to email"""
        headers = {
            'accept': '*/*',
            'accept-language': 'ru,en-US;q=0.9,en;q=0.8',
            'apikey': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xa3pqdmZkdWRzZWdnaWhmdW1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg1MjgyNDEsImV4cCI6MjA3NDEwNDI0MX0.jWIydqUPT70Y8A7ElWXpHu9qNJiCWW3zfxda9-Bso38',
            'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xa3pqdmZkdWRzZWdnaWhmdW1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg1MjgyNDEsImV4cCI6MjA3NDEwNDI0MX0.jWIydqUPT70Y8A7ElWXpHu9qNJiCWW3zfxda9-Bso38',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://dashboard.datahive.ai',
            'referer': 'https://dashboard.datahive.ai/',
            'user-agent': self.user_agent,
            'x-client-info': 'supabase-js-web/2.56.0',
            'x-supabase-api-version': '2024-01-01'
        }
        params = {
            'redirect_to': 'https://dashboard.datahive.ai/'
        }
        json_data = {
            'email': email,
            'data': {},
            'create_user': True,
            'gotrue_meta_security': {},
            'code_challenge': None,
            'code_challenge_method': None
        }
        return await self.send_request(
            request_type='POST',
            json_data=json_data,
            params=params,
            headers=headers,
            url='https://oqkzjvfdudseggihfump.supabase.co/auth/v1/otp'
        )

    async def verify_url(self, url: str) -> str:
        """Extract token from redirect URL"""
        response = await self.clear_request(url)
        location = response.headers.get('location')
        if not location:
            raise APIError('No location header found in the response')
        if not location.startswith('https://dashboard.datahive.ai/#access_token='):
            raise APIError(f'Invalid redirect URL: {location}')
        token = location.split('#access_token=')[1].split('&')[0]
        return token

    async def login(self, token: str):
        """Authenticate using token"""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://dashboard.datahive.ai',
            'Referer': 'https://dashboard.datahive.ai/',
            'User-Agent': self.user_agent
        }
        json_data = {
            'supabaseToken': token
        }
        response = await self.send_request(
            request_type='POST',
            json_data=json_data,
            headers=headers,
            url='https://api.datahive.ai/api/auth/login'
        )
        return response

    @require_auth_token
    async def complete_sign_up(self, referral_code: Optional[str] = None):
        """Complete registration with optional referral code"""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'ru,en-US;q=0.9,en;q=0.8',
            'authorization': f'Bearer {self.auth_token}',
            'origin': 'https://dashboard.datahive.ai',
            'referer': 'https://dashboard.datahive.ai/',
            'user-agent': self.user_agent
        }
        json_data = {'alias': referral_code} if referral_code else {}
        response = await self.send_request(
            request_type='POST',
            headers=headers,
            url='https://api.datahive.ai/api/user/sign-up/complete',
            json_data=json_data,
            verify=False
        )
        # If verify=False, Response object is returned
        if hasattr(response, 'text') and response.text.strip() != 'OK':
            raise APIError(f'Failed to complete sign up: {response.text}')

    @require_auth_token
    async def request_user(self):
        """Get user information"""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
            'Authorization': f'Bearer {self.auth_token}',
            'Connection': 'keep-alive',
            'Origin': 'https://dashboard.datahive.ai',
            'Referer': 'https://dashboard.datahive.ai/',
            'User-Agent': self.user_agent
        }
        return await self.send_request(
            request_type='GET',
            headers=headers,
            url='https://api.datahive.ai/api/user'
        )

    @require_auth_token
    async def get_referral_code(self) -> str:
        """Get user referral code"""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'ru,en-US;q=0.9,en;q=0.8',
            'authorization': f'Bearer {self.auth_token}',
            'origin': 'https://dashboard.datahive.ai',
            'referer': 'https://dashboard.datahive.ai/',
            'user-agent': self.user_agent
        }
        response = await self.send_request(
            request_type='GET',
            headers=headers,
            url='https://api.datahive.ai/api/user/referrals/aliases'
        )
        return response['items'][0]['alias']
    
    @require_auth_token
    async def send_ping(self, device: Device):
        """Send ping with device information"""
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Origin': 'chrome-extension://bonfdkhbkkdoipfojcnimjagphdnfedb',
            'User-Agent': device.user_agent,
            'authorization': f'Bearer {self.auth_token}',
            'content-type': 'application/json',
            'x-app-version': '0.2.5',
            'x-device-name': 'windows pc',
            'x-device-model': 'PC x86 - Chrome 142',
            'x-cpu-architecture': device.cpu_architecture,
            'x-cpu-model': device.cpu_model,
            'x-cpu-processor-count': str(device.cpu_processor_count),
            'x-device-id': device.device_id,
            'x-device-os': device.device_os,
            'x-device-type': 'extension',
            'x-s': 'f',
            'x-user-agent': device.user_agent,
            'x-user-language': 'ru'
        }
        return await self.send_request(
            request_type='POST',
            headers=headers,
            url='https://api.datahive.ai/api/ping'
        )

    @require_auth_token
    async def request_task(self, device: Device):
        """Request task for execution (API endpoint uses 'job')"""
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'User-Agent': device.user_agent,
            'authorization': f'Bearer {self.auth_token}',
            'content-type': 'application/json',
            'x-app-version': '0.2.5',
            'x-device-name': 'windows pc',
            'x-device-model': 'PC x86 - Chrome 142',
            'x-cpu-architecture': device.cpu_architecture,
            'x-cpu-model': device.cpu_model,
            'x-cpu-processor-count': str(device.cpu_processor_count),
            'x-device-id': device.device_id,
            'x-device-os': device.device_os,
            'x-device-type': 'extension',
            'x-s': 'f',
            'x-user-agent': device.user_agent,
            'x-user-language': 'ru'
        }
        return await self.send_request(
            request_type='GET',
            headers=headers,
            url='https://api.datahive.ai/api/job'
        )

    @require_auth_token
    async def complete_task(self, device: Device, task_id: str, json_data: dict):
        """Complete task execution (API endpoint uses 'job')"""
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Origin': 'chrome-extension://bonfdkhbkkdoipfojcnimjagphdnfedb',
            'User-Agent': device.user_agent,
            'authorization': f'Bearer {self.auth_token}',
            'content-type': 'application/json',
            'x-app-version': '0.2.5',
            'x-device-name': 'windows pc',
            'x-device-model': 'PC x86 - Chrome 142',
            'x-cpu-architecture': device.cpu_architecture,
            'x-cpu-model': device.cpu_model,
            'x-cpu-processor-count': str(device.cpu_processor_count),
            'x-device-id': device.device_id,
            'x-device-os': device.device_os,
            'x-device-type': 'extension',
            'x-s': 'f',
            'x-user-agent': device.user_agent,
            'x-user-language': 'ru'
        }
        return await self.send_request(
            request_type='POST',
            json_data=json_data,
            headers=headers,
            url=f'https://api.datahive.ai/api/job/{task_id}'
        )

    async def fetch_task_html(self, url: str, timeout: int = None) -> Optional[str]:
        """Fetch HTML content for task"""
        session = self._create_session()
        try:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ru,en-US;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Referer': url,
                'User-Agent': self.user_agent
            }
            response = await session.get(
                url,
                timeout=timeout,
                verify=False,
                allow_redirects=False,
                headers=headers
            )
            if response.status_code != 200:
                await session.close()
                return None
            text = response.text
            await session.close()
            return text
        except Exception:
            try:
                await session.close()
            except Exception:
                pass
            return None
    
    async def close(self) -> None:
        """Close session and clear token"""
        await self.close_session()
        self.auth_token = None
