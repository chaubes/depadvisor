"""File-based response cache for API calls."""

import hashlib
import json
import os
import time
from pathlib import Path


def _get_cache_dir() -> Path:
    """Get the cache directory, creating it if needed."""
    cache_dir = Path(os.environ.get("DEPADVISOR_CACHE_DIR", "~/.cache/depadvisor")).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cache_key(namespace: str, *parts: str) -> str:
    """Generate a cache key from namespace and parts."""
    raw = ":".join(parts)
    hashed = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{namespace}/{hashed}.json"


def cache_get(namespace: str, *parts: str, ttl_seconds: int = 86400) -> dict | None:
    """
    Read a cached value if it exists and hasn't expired.

    Args:
        namespace: Cache category (e.g., "pypi", "osv")
        parts: Key components (e.g., package name, version)
        ttl_seconds: Time-to-live in seconds (default 24h)

    Returns:
        Cached data dict, or None if miss/expired
    """
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / _cache_key(namespace, *parts)

    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        cached_at = data.get("_cached_at", 0)
        if time.time() - cached_at > ttl_seconds:
            cache_file.unlink(missing_ok=True)
            return None
        return data.get("_data")
    except (json.JSONDecodeError, OSError):
        return None


def cache_set(namespace: str, *parts: str, data: dict) -> None:
    """
    Write a value to the cache.

    Args:
        namespace: Cache category
        parts: Key components
        data: Data to cache
    """
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / _cache_key(namespace, *parts)
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "_cached_at": time.time(),
        "_data": data,
    }

    try:
        cache_file.write_text(json.dumps(payload))
    except OSError:
        pass  # Cache write failures are non-fatal


def cache_clear(namespace: str | None = None) -> int:
    """
    Clear cached data.

    Args:
        namespace: If provided, only clear this namespace. Otherwise clear all.

    Returns:
        Number of files removed
    """
    cache_dir = _get_cache_dir()
    count = 0

    if namespace:
        ns_dir = cache_dir / namespace
        if ns_dir.exists():
            for f in ns_dir.glob("*.json"):
                f.unlink()
                count += 1
    else:
        for f in cache_dir.rglob("*.json"):
            f.unlink()
            count += 1

    return count
