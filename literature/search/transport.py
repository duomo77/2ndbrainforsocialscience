"""
transport.py — Shared HTTP Transport for Literature Providers (EPIC 09)
=======================================================================
One polite, rate-aware HTTP layer shared by every provider:

  - requests.Session with descriptive User-Agent (academic APIs ask for one)
  - retry with exponential backoff + jitter on 429 / 5xx / timeouts
  - Retry-After header honoured for throttled endpoints (Semantic Scholar)
  - per-provider minimum request interval (arXiv asks for ~3 s courtesy)
  - every failure surfaces as ``TransportError`` (never a bare exception mix)

Providers receive a transport instance; tests inject fakes here, which keeps
the entire literature package network-free under test.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

DEFAULT_USER_AGENT = (
    "ROS-ScientificContext/1.0 (Research Operating System; "
    "literature expansion engine; contact: ros@localhost)"
)


class TransportError(RuntimeError):
    """Raised when an HTTP request fails after exhausting retries."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class TransportConfig:
    timeout: float = 25.0
    max_retries: int = 3
    backoff_base: float = 1.6
    backoff_cap: float = 12.0
    min_interval: float = 0.0  # polite pacing between consecutive requests
    user_agent: str = DEFAULT_USER_AGENT


_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpTransport:
    """Thin retrying GET wrapper around ``requests.Session``."""

    def __init__(self, config: Optional[TransportConfig] = None, session: Any = None):
        try:
            import requests  # noqa: F401
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "The literature package requires the 'requests' library. "
                "Install it with: pip install requests"
            ) from exc

        import requests as _requests

        self.config = config or TransportConfig()
        self._session = session or _requests.Session()
        self._session.headers.setdefault("User-Agent", self.config.user_agent)
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    # ── public API ─────────────────────────────────────────────────────────

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        response = self._get(url, params=params, headers=headers)
        try:
            return response.json()
        except ValueError as exc:
            raise TransportError(f"invalid JSON from {url}: {exc}") from exc

    def get_text(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        return self._get(url, params=params, headers=headers).text

    def close(self) -> None:
        self._session.close()

    # ── internals ──────────────────────────────────────────────────────────

    def _pace(self) -> None:
        if self.config.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._last_request_at + self.config.min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        import requests as _requests

        last_error: Optional[Exception] = None
        attempts = max(1, self.config.max_retries + 1)

        for attempt in range(attempts):
            self._pace()
            try:
                response = self._session.get(
                    url, params=params, headers=headers, timeout=self.config.timeout
                )
            except (_requests.Timeout, _requests.ConnectionError, OSError) as exc:
                last_error = exc
                self._sleep_backoff(attempt, retry_after=None)
                continue

            if response.status_code in _RETRYABLE_STATUS:
                last_error = TransportError(
                    f"HTTP {response.status_code} from {url}",
                    status_code=response.status_code,
                )
                if attempt < attempts - 1:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    self._sleep_backoff(attempt, retry_after=retry_after)
                    continue
                raise last_error

            if not response.ok:
                raise TransportError(
                    f"HTTP {response.status_code} from {url}: {response.text[:200]}",
                    status_code=response.status_code,
                )
            return response

        raise TransportError(f"request to {url} failed after retries: {last_error}")

    def _sleep_backoff(self, attempt: int, retry_after: Optional[float]) -> None:
        if retry_after is not None and retry_after > 0:
            delay = min(retry_after, self.config.backoff_cap)
        else:
            delay = min(self.config.backoff_base**attempt, self.config.backoff_cap)
            delay += random.uniform(0.0, 0.25 * delay)
        time.sleep(delay)


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
