#!/usr/bin/env python3
"""
Datahive Bot - Main Entry Point
"""

import asyncio
import sys
import signal
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config.settings import get_settings
from app.utils.logging import init_logger, get_logger
from app.app import DatahiveApp
from app.database import init_database, close_database
from app.utils.shutdown import get_shutdown_manager

shutdown_event: Optional[asyncio.Event] = None
_interrupt_handled = False


def handle_interrupt(signum, frame):
    """Signal handler - does not use logger to avoid deadlock"""
    global _interrupt_handled

    if not _interrupt_handled:
        _interrupt_handled = True
        #print("\nInterrupt received. Shutting down...")
        
        if shutdown_event is not None:
            shutdown_event.set()
        
        raise KeyboardInterrupt

    print("\nForcing exit...")
    sys.exit(1)


async def main():
    global shutdown_event
    
    settings = get_settings()
    init_logger(settings.logging_level)
    logger = get_logger()
    
    manager = None

    try:
        logger.info("Starting Datahive Bot...")
        
        await init_database()
        shutdown_event = asyncio.Event()
        get_shutdown_manager().initialize(shutdown_event)
        
        manager = DatahiveApp()
        await manager.run()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        if shutdown_event is not None:
            shutdown_event.set()
        if manager is not None:
            await manager.stop()
        await close_database()

        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Application shutdown complete")


if __name__ == "__main__":
    import os
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)
    
    def excepthook(exc_type, exc_value, exc_traceback):
        if exc_type == KeyboardInterrupt:
            return
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = excepthook
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except SystemExit:
        pass
    except Exception as e:
        print(f"Main error: {e}")
    
    # Force exit to kill any remaining threads
    os._exit(0)