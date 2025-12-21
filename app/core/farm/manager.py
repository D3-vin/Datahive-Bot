import asyncio
import multiprocessing
import platform
import sys
import time
from multiprocessing import Process
from typing import List, Dict

from app.utils.logging import get_logger
from app.utils.shutdown import is_shutdown_requested

logger = get_logger()


class MultiprocessFarmingManager:
    def __init__(self):
        self.processes: List[Process] = []
    
    def distribute_proxies(self, proxies: List[str], process_count: int) -> Dict[int, List[str]]:
        if not proxies:
            return {i: [] for i in range(process_count)}
            
        distributed_proxies = {}
        proxies_per_process = len(proxies) // process_count
        remainder = len(proxies) % process_count
        
        start_idx = 0
        for i in range(process_count):
            current_count = proxies_per_process + (1 if i < remainder else 0)
            end_idx = start_idx + current_count
            distributed_proxies[i] = proxies[start_idx:end_idx]
            start_idx = end_idx
            
        return distributed_proxies
    
    def get_optimal_process_count(self) -> int:
        from app.config.settings import get_settings
        
        settings = get_settings()
        cpu_count = multiprocessing.cpu_count()
        
        if settings.multiprocess_max_processes > 0:
            configured_count = settings.multiprocess_max_processes
            optimal_count = min(configured_count, max(1, cpu_count - 1))
        else:
            farming_threads = settings.farming_threads
            optimal_count = min(farming_threads, max(1, cpu_count - 1))
        return optimal_count
    
    async def start_multiprocess_farming(self, accounts: List[dict]) -> None:
        from app.database import load_proxies
        
        if not accounts:
            logger.error("No accounts provided for farming")
            return
        
        proxies = load_proxies()
        optimal_process_count = self.get_optimal_process_count()
        # Process count should not exceed account count
        process_count = min(optimal_process_count, len(accounts))
        
        if process_count < optimal_process_count:
            logger.info(f"Reduced process count from {optimal_process_count} to {process_count} (limited by account count)")
        
        accounts_per_process = len(accounts) // process_count
        distributed_proxies = self.distribute_proxies(proxies, process_count)
        
        logger.info(f"Starting farming with {process_count} CPU processes")
        logger.info(f"Total accounts: {len(accounts)}, Total proxies: {len(proxies)}")
        
        for i in range(process_count):
            start_idx = i * accounts_per_process
            if i < process_count - 1:
                end_idx = start_idx + accounts_per_process
            else:
                end_idx = len(accounts)
            
            process_accounts = accounts[start_idx:end_idx]
            process_proxies = distributed_proxies.get(i, [])
            
            if not process_accounts:
                continue
            
            logger.debug(f"Process {i}: {len(process_proxies)} proxies allocated")
            
            process = Process(
                target=self._run_farming_process,
                args=(i, process_accounts, process_proxies)
            )
            
            self.processes.append(process)
            process.start()
        
        await self._check_if_processes_alive()
    
    @staticmethod
    def _run_farming_process(process_id: int, accounts: List[dict], proxies: List[str]) -> None:
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        async def farming_worker():
            try:
                from app.utils.logging import get_logger
                from app.database import init_database, close_database
                from app.utils.proxy import get_proxy_manager
                from app.core.farm.processor import FarmProcessor
                
                process_logger = get_logger()
                process_logger.info(f'Process: {process_id} | Starting farming worker with {len(accounts)} accounts')
                
                await init_database()
                
                proxy_manager = get_proxy_manager()
                proxy_manager.load_proxies(proxies)
                
                processor = FarmProcessor(process_id, accounts)
                await processor.farm_continuously()
                
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except SystemExit as e:
                try:
                    process_logger = get_logger()
                    process_logger.info(f'Process: {process_id} | Exiting with code {e.code}')
                except Exception:
                    pass
            except Exception as e:
                try:
                    process_logger = get_logger()
                    process_logger.error(f"Process {process_id} error: {e}")
                except Exception:
                    pass
            finally:
                try:
                    await close_database()
                except Exception:
                    pass
        
        try:
            asyncio.run(farming_worker())
        except (KeyboardInterrupt, SystemExit):
            pass
    
    async def _check_if_processes_alive(self) -> None:
        while True:
            if is_shutdown_requested():
                logger.info("Shutdown requested, terminating processes...")
                self.stop()
                break
            
            if all(proc.is_alive() for proc in self.processes):
                try:
                    await asyncio.sleep(1)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    logger.info("Monitoring interrupted, terminating processes...")
                    self.stop()
                    break
                continue
            
            exited_processes = [proc for proc in self.processes if not proc.is_alive()]
            for exited_proc in exited_processes:
                logger.error(
                    f'Process with PID {exited_proc.pid} has exited unexpectedly. '
                    f'Terminating all processes.'
                )
            
            for proc in self.processes:
                if proc.is_alive():
                    proc.terminate()
            
            break
    
    def stop(self) -> None:
        if not self.processes:
            return
        
        logger.info(f"Terminating {len(self.processes)} processes...")
        
        for proc in self.processes:
            if proc.is_alive():
                try:
                    proc.terminate()
                except Exception:
                    pass
        
        time.sleep(0.5)
        
        for proc in self.processes:
            if proc.is_alive():
                try:
                    proc.kill()
                except Exception:
                    pass
        
        self.processes.clear()
        logger.info("All processes terminated")

