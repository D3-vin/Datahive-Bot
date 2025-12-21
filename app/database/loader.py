import os
from typing import List
from itertools import cycle

from app.utils.logging import get_logger
from app.utils.proxy import get_proxy_manager
from app.database.models.accounts import Account
from app.database.manager import DatabaseManager

logger = get_logger()


def load_accounts(file_name: str = "registration_accounts.txt") -> List[dict]:
    """
    Load accounts from file.
    Format: email:password:imap_server or email:password (imap_server determined automatically)
    """
    # Use absolute path relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(project_root, "config", "data", file_name)
    
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return []
    
    try:
        from app.config.settings import get_settings
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        accounts = []
        settings = get_settings()
        imap_servers = settings.imap_settings.get('servers', {})
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split(':')
            if len(parts) < 2:
                logger.warning(f"Invalid account format (expected email:password[:imap_server]): {line}")
                continue
            
            email = parts[0].strip()
            email_password = parts[1].strip()
            
            # Determine IMAP server
            if len(parts) >= 3:
                imap_server = parts[2].strip()
            else:
                # Automatic detection by email domain
                domain = email.split('@')[-1] if '@' in email else ''
                imap_server = imap_servers.get(domain, 'imap.gmail.com')  # Default to Gmail
            
            accounts.append({
                'email': email,
                'email_password': email_password,
                'imap_server': imap_server
            })
        
        logger.info(f"Loaded {len(accounts)} accounts from {file_name}")
        return accounts
        
    except Exception as e:
        logger.error(f"Error loading accounts from {file_name}: {e}")
        return []


def load_farm_accounts(file_name: str = "farming_accounts.txt") -> List[str]:
    """
    Load account emails for farming from file.
    Format: email only (no password), one per line
    Used to find accounts in database
    """
    # Use absolute path relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(project_root, "config", "data", file_name)
    
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        emails = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # If format is email:password, take only email
            if ':' in line:
                email = line.split(':')[0].strip()
            else:
                email = line.strip()
            
            # Check that this is an email (contains @)
            if '@' in email:
                emails.append(email)
            else:
                logger.warning(f"Invalid email format in {file_name}: {line}")
        
        logger.info(f"Loaded {len(emails)} emails from {file_name}")
        return emails
        
    except Exception as e:
        logger.error(f"Error loading farm accounts from {file_name}: {e}")
        return []


def load_proxies() -> List[str]:
    # Use absolute path relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(project_root, "config", "data", "proxy.txt")
    
    if not os.path.exists(file_path):
        logger.error(f"Proxy file not found: {file_path}")
        raise FileNotFoundError(f"Proxy file is required: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        proxies = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                if not line.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                    line = f"http://{line}"
                proxies.append(line)
        
        if not proxies:
            raise ValueError("No valid proxies found in proxy file")
        
        logger.debug(f"Loaded {len(proxies)} proxies")
        return proxies
        
    except Exception as e:
        logger.error(f"Error loading proxies: {e}")
        raise


def get_proxy_for_account(proxies: List[str], account_index: int) -> str:
    if not proxies:
        raise ValueError("Proxies are required but no proxies loaded")
    
    proxy_cycle = cycle(proxies)
    for _ in range(account_index):
        next(proxy_cycle)
    
    return next(proxy_cycle)


def load_twitter_tokens() -> List[str]:
    # Use absolute path relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(project_root, "config", "data", "twitter_token.txt")
    
    if not os.path.exists(file_path):
        logger.warning(f"Twitter tokens file not found: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        tokens = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                tokens.append(line)
        
        logger.info(f"Loaded {len(tokens)} Twitter tokens")
        return tokens
        
    except Exception as e:
        logger.error(f"Error loading Twitter tokens: {e}")
        return []


def initialize_proxy_manager() -> None:
    try:
        proxies = load_proxies()
        if not proxies:
            logger.warning("No proxies loaded from file - proxy rotation will not work")
            return
        
        manager = get_proxy_manager()
        manager.load_proxies(proxies)
    except Exception as e:
        logger.error(f"Failed to initialize proxy manager: {e}")
        raise


async def get_proxy_stats() -> dict:
    manager = get_proxy_manager()
    return await manager.get_stats()


async def load_accounts_from_database() -> List[Account]:
    try:
        accounts = await Account.get_all_accounts()
        logger.info(f"Loaded {len(accounts)} accounts from database")
        return accounts
    except Exception as e:
        logger.error(f"Error loading accounts from database: {e}")
        return []



