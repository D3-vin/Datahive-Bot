"""Centralized shutdown management for Datahive"""

import asyncio
from typing import Optional


class ShutdownManager:
    """Manager storing global shutdown event"""

    def __init__(self) -> None:
        self._shutdown_event: Optional[asyncio.Event] = None
        self._initialized = False

    def initialize(self, shutdown_event: asyncio.Event) -> None:
        """Bind external shutdown event"""
        self._shutdown_event = shutdown_event
        self._initialized = True

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown is requested"""
        if not self._initialized or not self._shutdown_event:
            return False
        return self._shutdown_event.is_set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown event"""
        if self._initialized and self._shutdown_event:
            await self._shutdown_event.wait()

    def should_continue(self) -> bool:
        """True if execution can continue"""
        return not self.is_shutdown_requested()


_shutdown_manager = ShutdownManager()


def get_shutdown_manager() -> ShutdownManager:
    """Get global shutdown manager"""
    return _shutdown_manager


def is_shutdown_requested() -> bool:
    """Convenient shortcut to check shutdown"""
    return _shutdown_manager.is_shutdown_requested()


def should_continue() -> bool:
    """Convenient shortcut to check if should continue"""
    return _shutdown_manager.should_continue()
