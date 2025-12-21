import asyncio
from collections import deque
from typing import Optional, List

from app.utils.logging import get_logger

logger = get_logger()


class ProxyManager:
    """Simple proxy manager with circular rotation"""
    
    def __init__(self):
        self.proxies: deque = deque()
        self.lock = asyncio.Lock()
        
    def load_proxies(self, proxy_urls: List[str]) -> None:
        self.proxies = deque([url.strip() for url in proxy_urls if url.strip()])
    
    async def get_proxy(self) -> Optional[str]:
        async with self.lock:
            if not self.proxies:
                logger.warning("No available proxies")
                return None
            
            proxy = self.proxies.popleft()
            return proxy
    
    async def release_proxy(self, proxy: Optional[str]) -> None:
        if not proxy:
            return
        async with self.lock:
            self.proxies.append(proxy)
    
    async def remove_proxy(self, proxy: Optional[str]) -> bool:
        if not proxy:
            return False
        async with self.lock:
            try:
                self.proxies.remove(proxy)
                logger.info("Removed bad proxy from pool")
                return True
            except ValueError:
                return False
    
    def get_stats(self) -> dict:
        return {"total": len(self.proxies)}


_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager() -> ProxyManager:
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager
