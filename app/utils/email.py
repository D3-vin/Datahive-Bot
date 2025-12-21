"""
Утилиты для работы с IMAP (валидация email, извлечение ссылок из писем)
"""

import os
import ssl
import re
import asyncio
from typing import Optional, Dict
from datetime import datetime, timezone
from imap_tools import MailBox, AND, MailboxLoginError
from imaplib import IMAP4, IMAP4_SSL
from python_socks.sync import Proxy as SyncProxy

from app.utils.logging import get_logger

logger = get_logger()

os.environ['SSLKEYLOGFILE'] = ''


class IMAP4Proxy(IMAP4):
    """IMAP4 client with proxy support"""
    
    def __init__(self, host: str, proxy: Optional[str] = None, port: int = 143, rdns: bool = True, timeout: float = None):
        self._host = host
        self._port = port
        self._proxy = proxy
        if proxy:
            self._pysocks_proxy = SyncProxy.from_url(proxy, rdns=rdns)
        super().__init__(host, port, timeout)
    
    def _create_socket(self, timeout):
        """Create socket through proxy"""
        return self._pysocks_proxy.connect(self._host, self._port, timeout)


class IMAP4SSlProxy(IMAP4Proxy):
    """IMAP4 SSL client with proxy support"""
    
    def __init__(self, host: str, proxy: Optional[str] = None, port: int = 993, rdns: bool = True, ssl_context: ssl.SSLContext = None, timeout: float = None):
        if ssl_context is None:
            self.ssl_context = ssl._create_unverified_context()
        else:
            self.ssl_context = ssl_context
        super().__init__(host, proxy, port, rdns, timeout)
    
    def _create_socket(self, timeout):
        """Create SSL socket through proxy"""
        sock = super()._create_socket(timeout)
        server_hostname = self.host if ssl.HAS_SNI else None
        return self.ssl_context.wrap_socket(sock, server_hostname=server_hostname)


class MailBoxClient(MailBox):
    """Client for working with mailbox through proxy"""
    
    def __init__(self, host: str, proxy: Optional[str] = None, port: int = 993, timeout: float = None, rdns: bool = True, ssl_context: ssl.SSLContext = None):
        self._proxy = proxy
        self._rdns = rdns
        super().__init__(host, port, timeout, ssl_context)
    
    def _get_mailbox_client(self):
        """Get mailbox client with or without proxy"""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        if self._proxy:
            return IMAP4SSlProxy(
                self._host,
                self._proxy,
                port=self._port,
                rdns=self._rdns,
                timeout=self._timeout,
                ssl_context=ssl_context
            )
        else:
            return IMAP4_SSL(
                self._host,
                port=self._port,
                timeout=self._timeout,
                ssl_context=ssl_context
            )


class EmailValidator:
    """Email account validator via IMAP"""
    
    def __init__(self, imap_server: str, email: str, password: str):
        self.imap_server = imap_server
        self.email = email
        self.password = password
    
    async def validate(self, proxy: Optional[str] = None) -> Dict:
        """Validate email and password via IMAP"""
        logger.info(f'Checking if email is valid...', self.email)
        
        def login_sync():
            """Synchronous login function"""
            mailbox = MailBoxClient(self.imap_server, proxy=proxy, timeout=30)
            mailbox.login(self.email, self.password)
            return True
        
        try:
            await asyncio.to_thread(login_sync)
            return {
                'status': True,
                'identifier': self.email,
                'data': f'Valid: {datetime.now()}',
                'error': ''
            }
        except MailboxLoginError:
            return {
                'status': False,
                'identifier': self.email,
                'data': None,
                'error': 'Invalid credentials'
            }
        except Exception as error:
            logger.error(f'Email validation failed: {str(error)}', self.email)
            return {
                'status': False,
                'identifier': self.email,
                'data': None,
                'error': f'Validation failed: {str(error)}'
            }


class LinkCache:
    """Cache for tracking used links"""
    
    def __init__(self):
        self._used_links = {}
    
    def is_link_used(self, link: str) -> bool:
        """Check if link was used before"""
        return link in self._used_links
    
    def add_link(self, email: str, link: str) -> None:
        """Add link to cache"""
        self._used_links[link] = email


class LinkExtractor:
    """Extract verification links from emails via IMAP"""
    
    _link_cache = LinkCache()
    
    def __init__(
        self,
        imap_server: str,
        email: str,
        password: str,
        max_attempts: int = 3,
        delay_seconds: int = 5,
        redirect_email: Optional[str] = None
    ):
        self.imap_server = imap_server
        self.email = email
        self.password = password
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.redirect_email = redirect_email
        self.link_patterns = [
            r'https://[a-z0-9-]+\.supabase\.co/auth/v1/verify\?token=([0-9a-f]+)(?:&|&amp;)type=(?:signup|magiclink)(?:&|&amp;)redirect_to=https://dashboard\.datahive\.ai/?'
        ]
    
    async def extract_link(self, proxy: Optional[str] = None) -> Dict:
        """Extract verification link from emails with retries"""
        return await self.search_with_retries(proxy)
    
    def _collect_messages(self, mailbox: MailBox) -> list:
        """Collect messages from mailbox"""
        messages = []
        
        allowed_exact = {'noreply@datahive.ai'}
        
        def to_from_prefix(email_like: str) -> str:
            """Convert email-like string to prefix"""
            s = email_like.strip().lower()
            s = s.replace('-', '_')
            s = s.replace('@', '_at_')
            s = s.replace('.', '_')
            return s
        
        allowed_prefix = {to_from_prefix(e) for e in allowed_exact}
        
        # Search for messages from exact addresses
        for sender in allowed_exact:
            try:
                for msg in mailbox.fetch(AND(from_=sender), reverse=True, limit=10, mark_seen=True):
                    if self.redirect_email and self.redirect_email != msg.to[0]:
                        continue
                    
                    msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                    messages.append((msg, msg_date))
            except Exception:
                pass
        
        # Search for messages with prefixes
        try:
            for msg in mailbox.fetch(reverse=True, limit=10, mark_seen=True):
                f = (msg.from_ or '').lower()
                if any(f.startswith(p) for p in allowed_prefix) or f in allowed_exact:
                    if self.redirect_email and self.redirect_email != msg.to[0]:
                        continue
                    
                    msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                    messages.append((msg, msg_date))
        except Exception:
            pass
        
        return messages
    
    def _process_latest_message(self, messages: list) -> Optional[str]:
        """Process latest message and extract link"""
        if not messages:
            return None
        
        try:
            if self.redirect_email:
                filtered_messages = [(msg, date) for msg, date in messages if self.redirect_email in msg.to]
                if not filtered_messages:
                    return None
                latest_msg, latest_date = max(filtered_messages, key=lambda x: x[1])
            else:
                latest_msg, latest_date = max(messages, key=lambda x: x[1])
        except (ValueError, AttributeError):
            return None
        
        # Check message age (not older than 300 seconds)
        msg_age = (datetime.now(timezone.utc) - latest_date).total_seconds()
        if msg_age > 300:
            return None
        
        body = latest_msg.text or latest_msg.html
        if not body:
            return None
        
        # Search for link by patterns
        for pattern in self.link_patterns:
            match = re.search(pattern, body)
            if match:
                code = str(match.group(0))
                
                # Check cache
                if self._link_cache.is_link_used(code):
                    return None
                
                self._link_cache.add_link(self.email, code)
                return code
        
        return None
    
    async def _search_in_all_folders(self, proxy: Optional[str] = None) -> Optional[str]:
        """Search for link in all mailbox folders"""
        def search_in():
            """Synchronous function for searching in folders"""
            all_messages = []
            with MailBoxClient(host=self.imap_server, proxy=proxy, timeout=30).login(self.email, self.password) as mailbox:
                for folder in mailbox.folder.list():
                    try:
                        if mailbox.folder.exists(folder.name):
                            mailbox.folder.set(folder.name)
                            messages = self._collect_messages(mailbox)
                            all_messages.extend(messages)
                    except Exception as e:
                        continue
                
                if all_messages:
                    return self._process_latest_message(all_messages)
            return None
        
        return await asyncio.to_thread(search_in)
    
    async def search_with_retries(self, proxy: Optional[str] = None) -> Dict:
        """Search for link with retries"""
        for attempt in range(self.max_attempts):
            link = await self._search_in_all_folders(proxy)
            if link:
                return self._create_success_result(link)
            
            if attempt < self.max_attempts - 1:
                logger.info(f'Code not found | Retrying in {self.delay_seconds} seconds | Attempt: {attempt + 1}/{self.max_attempts}', self.email)
                await asyncio.sleep(self.delay_seconds)
        
        logger.error(f'Max attempts reached, code not found in any folder', self.email)
        return {
            'status': False,
            'identifier': self.email,
            'data': 'Max attempts reached',
            'error': 'Max attempts reached'
        }
    
    def _create_success_result(self, link: str) -> Dict:
        """Create successful link extraction result"""
        return {
            'status': True,
            'identifier': self.email,
            'data': link,
            'error': ''
        }

