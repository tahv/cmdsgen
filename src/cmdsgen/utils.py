from __future__ import annotations

import asyncio
import itertools
import logging
from contextlib import asynccontextmanager
from functools import cache
from typing import TYPE_CHECKING, Final

from aiohttp import ClientSession
from aiohttp_client_cache import (  # type: ignore[attr-defined]
    CachedSession,
    SQLiteBackend,
)
from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

logger: Final[logging.Logger] = logging.getLogger("cmdsgen")
"""Application logger."""


def clamp(n: int, lo: int, hi: int) -> int:
    """Clamp `n` between `lo` and `hi`."""
    return min(max(n, lo), hi)


@cache
def stderr_console() -> Console:
    """Return the global stderr `Console`. Do **not** modify the console properties."""
    return Console(stderr=True, highlight=False)


@asynccontextmanager
async def Session(*, cached: bool) -> AsyncIterator[ClientSession]:  # noqa: N802
    """Session context wrapper."""
    session = (
        CachedSession(cache=SQLiteBackend(".cmdsgen-cache"))
        if cached
        else ClientSession()
    )
    async with session:
        yield session


async def fetch(session: ClientSession, url: str) -> tuple[str, str]:
    """Returns text content from url."""
    logger.debug("Fetching %s", url)
    async with session.get(url) as response:
        if response.status != 200:  # noqa: PLR2004
            response.raise_for_status()
        return (url, await response.text())


async def fetch_batched(
    session: ClientSession,
    urls: Iterable[str],
    n: int,
) -> AsyncIterator[tuple[str, str]]:
    """Fetch `urls` in batch of `n` length."""
    for batch in itertools.batched(urls, n, strict=False):
        for url, text in await asyncio.gather(*[fetch(session, u) for u in batch]):
            yield url, text
