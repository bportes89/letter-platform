"""Cache simples de tokens OAuth/Bearer para provedores externos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class CachedToken:
    value: str
    expires_at: datetime

    def valid(self) -> bool:
        return datetime.now(UTC) < self.expires_at


_cache: dict[str, CachedToken] = {}


def get_cached_token(key: str) -> str | None:
    item = _cache.get(key)
    if item and item.valid():
        return item.value
    return None


def set_cached_token(key: str, value: str, *, expires_in_seconds: int = 3300) -> None:
    _cache[key] = CachedToken(
        value=value,
        expires_at=datetime.now(UTC) + timedelta(seconds=max(60, expires_in_seconds - 60)),
    )
