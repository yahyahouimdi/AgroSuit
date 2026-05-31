"""Small HTTP helper with retries and an on-disk JSON cache.

Climate archives never change, so caching responses makes repeated analyses
instant and keeps the project usable during API outages.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from src.config import CACHE_DIR, HTTP_TIMEOUT, USER_AGENT


class DataSourceError(RuntimeError):
    """Raised when an external data source cannot be reached or parsed."""


def _cache_path(url: str, params: dict) -> Path:
    key = json.dumps({"url": url, "params": params}, sort_keys=True, default=str)
    return CACHE_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.json"


def get_json(url: str, params: dict, *, use_cache: bool = True, retries: int = 3, timeout: int = HTTP_TIMEOUT):
    path = _cache_path(url, params)
    if use_cache and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            path.unlink(missing_ok=True)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 429:
                # Free APIs enforce per-minute quotas: wait for the window to reset.
                last_err = DataSourceError(f"rate limit reached (HTTP 429) at {url}")
                if attempt < retries - 1:
                    time.sleep(20 * (attempt + 1))
                continue
            if resp.status_code >= 500:
                raise DataSourceError(f"HTTP {resp.status_code} from {url}")
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (requests.RequestException, ValueError, DataSourceError) as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise DataSourceError(f"Could not fetch {url}: {last_err}") from last_err
