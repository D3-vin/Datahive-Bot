import asyncio
import random
from typing import List

from app.ui.menu import get_menu
from app.utils.logging import get_logger
from app.database import (
    load_accounts, load_proxies, initialize_proxy_manager,
    load_accounts_from_database,
    initialize_database, close_database
)
from app.utils.proxy import get_proxy_manager
from app.utils.results import initialize_results
from app.core.modules.executor import ModuleExecutor
from app.core.farm import MultiprocessFarmingManager
from app.config.settings import get_settings
from app.database.models.accounts import Account

logger = get_logger()


class DatahiveApp:
    def __init__(self):
        self.menu = get_menu()
        self.settings = get_settings()
        self.running = True
        self.database_initialized = False
    
    async def run(self) -> None:
        await self._initialize_database()
        
        while self.running:
            try:
                self.menu.show_welcome()
                choice = self.menu.show_menu()
                
                if choice == 1:
                    await self._handle_registration()
                elif choice == 2:
                    await self._handle_farming()
                elif choice == 3:
                    self.running = False
                    logger.info("Shutting down...")
                    break
                elif choice == 4:
                    self.running = False
                    logger.info("Shutting down...")
                    break
                
                if self.running:
                    input("Press Enter to continue...")
                    
            except KeyboardInterrupt:
                self.running = False
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Application error: {e}")
                input("Press Enter to continue...")
        
        await self._cleanup()
    
    async def _handle_registration(self) -> None:
        accounts = load_accounts("registration_accounts.txt")
        if not accounts:
            logger.error("No accounts found in registration_accounts.txt")
            return
        
        proxies = load_proxies()
        # Initialize proxy manager for rotation
        try:
            initialize_proxy_manager()
        except Exception as e:
            logger.warning(f"Failed to initialize proxy manager: {e}. Proxy rotation may not work.")
        
        self.menu.show_operation_info("Registration", len(accounts))
        
        semaphore = asyncio.Semaphore(self.settings.registration_threads)
        
        async def process_account(account_data: dict, index: int) -> bool:
            async with semaphore:
                delay = random.randint(self.settings.delay_min, self.settings.delay_max)
                if delay > 0:
                    logger.info(f"Waiting {delay}s before registration", account_data['email'])
                    await asyncio.sleep(delay)
                
                from app.utils.proxy import get_proxy_manager
                proxy_manager = get_proxy_manager()
                proxy = await proxy_manager.get_proxy()
                
                executor = ModuleExecutor(
                    email=account_data['email'],
                    email_password=account_data['email_password'],
                    imap_server=account_data['imap_server'],
                    proxy=proxy,
                    account_index=index
                )
                return await executor.process_registration()
        
        tasks = [process_account(account_data, i) for i, account_data in enumerate(accounts)]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            logger.info("Registration interrupted")
            return
        
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Registration task #{idx + 1} failed: {result}")
        
        success_count = sum(1 for r in results if r is True)
        failed_count = sum(1 for r in results if r is False or isinstance(r, Exception))
        
        logger.info(f"Registration completed: {success_count} processed, {failed_count} failed")
    
    async def _handle_farming(self) -> None:
        from app.database.loader import load_farm_accounts
        farm_emails = load_farm_accounts("farming_accounts.txt")
        
        db_accounts = []
        
        if farm_emails:
            for email in farm_emails:
                account = await Account.get_account(email)
                if account:
                    if not account.auth_token:
                        logger.warning(f"Account {email} not logged in. Skipped for farming.")
                        continue
                    db_accounts.append(account)
                else:
                    logger.warning(f"Account {email} not found in database. Skipped for farming.")
        else:
            logger.info("No valid emails in farming_accounts.txt, loading all accounts from database...")
            all_accounts = await load_accounts_from_database()
            for account in all_accounts:
                if account.auth_token:
                    db_accounts.append(account)
                else:
                    logger.debug(f"Account {account.email} not logged in. Skipped for farming.")
        
        if not db_accounts:
            logger.error("No valid accounts found in database for farming (accounts must have auth_token)")
            return
        
        accounts_data = []
        for account in db_accounts:
            accounts_data.append({
                'email': account.email,
                'email_password': account.email_password,
                'imap_server': account.imap_server
            })
        
        self.menu.show_operation_info("Farming", len(accounts_data))
        
        if self.settings.multiprocess_farming_enabled:
            logger.debug("Using multiprocess farming mode")
            await self._handle_multiprocess_farming(accounts_data)
        else:
            logger.debug("Using single process farming mode")
            await self._handle_single_process_farming(accounts_data)
    
    async def _handle_multiprocess_farming(self, accounts: List[dict]) -> None:
        logger.debug("Starting multiprocess farming mode")
        
        try:
            initialize_proxy_manager()
        except Exception as e:
            logger.error(f"Failed to initialize proxy manager: {e}")
            return
        
        farming_manager = MultiprocessFarmingManager()
        
        try:
            await farming_manager.start_multiprocess_farming(accounts)
        except KeyboardInterrupt:
            logger.info("Multiprocess farming interrupted, stopping processes...")
            farming_manager.stop()
            return
        except Exception as e:
            logger.error(f"Multiprocess farming error: {e}")
            farming_manager.stop()
    
    async def _handle_single_process_farming(self, accounts: List[dict]) -> None:
        logger.info("Starting single process farming mode")
        
        proxies = load_proxies()
        proxy_manager = get_proxy_manager()
        proxy_manager.load_proxies(proxies)
        
        total_accounts = len(accounts)
        semaphore = asyncio.Semaphore(self.settings.farming_threads)
        
        async def process_account(account_data: dict, index: int) -> None:
            async with semaphore:
                delay = random.randint(self.settings.delay_min, self.settings.delay_max)
                if delay > 0:
                    await asyncio.sleep(delay)
                
                from app.database.models.accounts import Account
                account = await Account.get_account(account_data['email'])
                proxy = account.active_account_proxy if account and account.active_account_proxy else None
                
                if not proxy:
                    proxy = await proxy_manager.get_proxy()
                
                executor = ModuleExecutor(
                    email=account_data['email'],
                    email_password=account_data['email_password'],
                    imap_server=account_data['imap_server'],
                    proxy=proxy,
                    account_index=index
                )
                try:
                    await executor.process_farming()
                finally:
                    pass
        
        tasks = [process_account(account_data, i) for i, account_data in enumerate(accounts)]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Farming interrupted")
        except Exception as e:
            logger.error(f"Farming error: {e}")
    
    async def _initialize_database(self) -> None:
        if self.database_initialized:
            return
        
        try:
            await initialize_database()
            self.database_initialized = True
            logger.success("Database initialized")
            
            await initialize_results()
            
            accounts = await load_accounts_from_database()
            logger.info(f"Found {len(accounts)} accounts in database")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def _cleanup(self) -> None:
        try:
            if self.database_initialized:
                await close_database()
                logger.debug("Database connections closed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    async def stop(self) -> None:
        self.running = False
        await self._cleanup()
        logger.info("Application stopped")
        logger.info("Application stopped")
