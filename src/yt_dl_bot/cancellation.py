"""Cooperative cancellation primitives for blocking download work.

Cancelling the asyncio caller signals the worker; it does not terminate the
thread created by :func:`asyncio.to_thread`. Blocking integrations must observe
the token at explicit boundaries before they can stop.
"""

import asyncio
import threading
from collections.abc import Callable


class DownloadCancelled(Exception):
    """A blocking download observed a cancellation request."""


class CancellationToken:
    """Thread-safe cancellation signal shared with blocking workers."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise DownloadCancelled("Download cancelled")

    def wait(self, timeout: float) -> None:
        """Wait for *timeout*, raising when cancellation wakes the wait."""
        if self._event.wait(timeout):
            self.raise_if_cancelled()


async def to_thread_cancellable[R](
    function: Callable[..., R],
    /,
    *args: object,
    **kwargs: object,
) -> R:
    """Run blocking work and signal it when the asyncio caller is cancelled.

    The caller receives :class:`asyncio.CancelledError` immediately. The worker
    thread continues until ``function`` observes ``cancellation_token``.
    """
    token = CancellationToken()
    kwargs["cancellation_token"] = token
    try:
        return await asyncio.to_thread(function, *args, **kwargs)
    except asyncio.CancelledError:
        token.cancel()
        raise
