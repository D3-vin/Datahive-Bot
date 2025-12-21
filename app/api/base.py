import asyncio
import json
from typing import Dict, Any, Optional, Literal, Union
from curl_cffi.requests import AsyncSession, Response
from app.core.exceptions import (
    APIError,
    ServerError,
    ProxyForbidden,
    RateLimitExceeded
)
from app.utils.logging import get_logger

logger = get_logger()


class BaseAPIClient:
    def __init__(self, api_url: str = None, proxy: Optional[str] = None):
        self.API_URL = api_url
        self.proxy = proxy
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
        self.session = self._create_session()

    def _create_session(self) -> AsyncSession:
        session = AsyncSession(
            impersonate='chrome142',
            verify=False,
            timeout=30
        )
        
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": self.user_agent
        })
        
        if self.proxy:
            session.proxies = {"http": self.proxy, "https": self.proxy}
        
        return session

    @staticmethod
    async def _verify_response(response_data: dict | list) -> None:
        if not isinstance(response_data, dict):
            return None
        
        if 'success' in response_data and response_data.get('success') is False:
            raise APIError(f'API returned an error: {response_data}', response_data)
        
        if 'error' in response_data and response_data.get('error'):
            raise APIError(f'API returned an error: {response_data}', response_data)
        
        return None

    async def close_session(self) -> None:
        try:
            if self.session:
                await self.session.close()
        except Exception:
            pass

    async def clear_request(self, url: str, timeout: int = None) -> Response:
        """Execute GET request without response validation (for redirects)"""
        try:
            session = self._create_session()
            response = await session.get(
                url,
                allow_redirects=False,
                verify=False,
                timeout=timeout or 30
            )
            await session.close()
            return response
        except Exception as error:
            try:
                await session.close()
            except Exception:
                pass
            raise error

    async def send_request(
        self,
        request_type: Literal['POST', 'GET', 'OPTIONS', 'PATCH'],
        method: str = None,
        json_data: dict = None,
        params: dict = None,
        url: str = None,
        headers: dict = None,
        cookies: dict = None,
        verify: bool = True,
        max_retries: int = 2,
        retry_delay: float = 3
    ) -> dict | Response:
        if not url:
            if not self.API_URL:
                raise ValueError('API_URL is not set')
            if not method:
                raise ValueError('Either url or method must be provided')
            url = f'{self.API_URL}{method}'
        
        for attempt in range(max_retries):
            try:
                if request_type == 'POST':
                    response = await self.session.post(
                        url,
                        json=json_data,
                        params=params,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies
                    )
                elif request_type == 'OPTIONS':
                    response = await self.session.options(
                        url,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies
                    )
                elif request_type == 'PATCH':
                    response = await self.session.patch(
                        url,
                        json=json_data,
                        params=params,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies
                    )
                else:
                    response = await self.session.get(
                        url,
                        params=params,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies
                    )
                
                if verify:
                    if response.headers.get('ratelimit-remaining') and response.headers.get('ratelimit-reset'):
                        reset_time = int(response.headers.get('ratelimit-reset'))
                        remaining = int(response.headers.get('ratelimit-remaining'))
                        if remaining in (0, 1):
                            raise RateLimitExceeded(reset_time)
                    
                    if response.status_code == 403:
                        if '403 Forbidden' in response.text:
                            raise ProxyForbidden(f'Proxy forbidden - {response.status_code}')
                    
                    if response.status_code == 403:
                        raise Exception(f'Response forbidden - 403: {response.text[:200]}')
                    
                    if response.status_code == 429:
                        raise APIError(f'Rate limit exceeded - {response.status_code}', response.text)
                    
                    if response.status_code in (500, 502, 503, 504):
                        raise ServerError(f'Server error - {response.status_code} | Response: {response.text[:200]}')
                    
                    try:
                        response_json = response.json()
                        await self._verify_response(response_json)
                        return response_json
                    except json.JSONDecodeError:
                        if response.status_code == 304:
                            return {}
                        raise Exception(f'Failed to decode response, most likely server error: {response.text[:200]}')
                else:
                    return response
                    
            except ServerError as error:
                if attempt == max_retries - 1:
                    raise error
                await asyncio.sleep(retry_delay)
                continue
            except (APIError, ProxyForbidden, RateLimitExceeded):
                raise
            except Exception as error:
                error_str = str(error)
                error_lower = error_str.lower()
                error_type = type(error).__name__
                
                if 'Proxy Authentication Required' in error_str or '407' in error_str:
                    raise
                
                if any(keyword in error_lower for keyword in [
                    'connection', 'connect', 'timeout', 'timed out', 
                    'network', 'unreachable', 'refused', 'reset',
                    'curl', 'ssl', 'tls', 'tunnel', 'failed to connect',
                    'connection aborted', 'connection reset', 'connection refused'
                ]) or 'RequestError' in error_type or 'CurlError' in error_type:
                    if attempt == max_retries - 1:
                        raise error
                    await asyncio.sleep(retry_delay)
                    continue
                
                if attempt == max_retries - 1:
                    raise error
                await asyncio.sleep(retry_delay)
                continue
        
        raise Exception(f'Failed to send request after {max_retries} attempts')


