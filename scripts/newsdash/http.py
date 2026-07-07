"""Shared HTTP session: UA, retries, and a default timeout every fetcher uses."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import __version__

USER_AGENT = f"personal-newsdash/{__version__} (GitHub Pages dashboard pipeline)"
DEFAULT_TIMEOUT = 20


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        # Never sleep on server-suggested Retry-After: rate-limited APIs
        # (OpenAlex, S2) send 60s+ values that would stall the whole build.
        respect_retry_after_header=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    resp = session.get(url, **kwargs)
    resp.raise_for_status()
    return resp
