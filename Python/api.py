#!/usr/bin/env python3
"""
Python helper for TOD Markets API.

Install dependencies:
    pip install requests python-dotenv

Usage:
    # set up .env or export env vars
    python Python/api.py
    # or import in code:
    from Python.api import get_tod_markets_endpoint, post_tod_markets_endpoint

This module provides:
- get_tod_markets_endpoint(endpoint, parameters=None)
- post_tod_markets_endpoint(endpoint, payload=None)
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; environment variables will still work
    pass

API_KEY = os.getenv("API_KEY")
DOMAIN_URL = os.getenv("DOMAIN_URL")

if not API_KEY:
    raise SystemExit("Missing API_KEY in environment. Please set API_KEY in your .env file or environment.")

if not DOMAIN_URL:
    raise SystemExit("Missing DOMAIN_URL in environment. Please set DOMAIN_URL in your .env file or environment.")

_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

__all__ = ["get_tod_markets_endpoint", "post_tod_markets_endpoint"]


def _build_url(endpoint: str, parameters: Optional[Union[Dict[str, Any], str]] = None) -> str:
    """Builds a full URL for the request.

    Parameters can be provided as a dict (values may be lists, which will repeat keys)
    or as a raw query string (e.g. '?limit=10').
    """
    url = urljoin(DOMAIN_URL, endpoint)

    if not parameters:
        return url

    if isinstance(parameters, str):
        qs = parameters.lstrip("?")
        if not qs:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{qs}"

    if isinstance(parameters, dict):
        qs = urlencode(parameters, doseq=True)
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{qs}" if qs else url

    raise TypeError("parameters must be a dict or query string")


def get_tod_markets_endpoint(endpoint: str, parameters: Optional[Union[Dict[str, Any], str]] = None) -> str:
    """Fetches an endpoint and returns the response body as text.

    Raises requests.HTTPError for non-2xx responses.

    Example:
        get_tod_markets_endpoint('/company', {'limit': 10, 'filter': 'active'})
        get_tod_markets_endpoint('/company', '?limit=10')
    """
    url = _build_url(endpoint, parameters)
    resp = requests.get(url, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


def post_tod_markets_endpoint(endpoint: str, payload: Any = None) -> str:
    """POSTs JSON payload to an endpoint and returns the response body as text.

    Raises requests.HTTPError for non-2xx responses.

    Example:
        post_tod_markets_endpoint('/company', {'name': 'Acme', 'active': True})
    """
    url = urljoin(DOMAIN_URL, endpoint)
    resp = requests.post(url, json=payload or {}, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


if __name__ == "__main__":
    # Quick demo when running the file directly
    print("GET /api/company")
    try:
        print(get_tod_markets_endpoint('/api/company'))
        print(get_tod_markets_endpoint('/api/assets/prices', {'markets': 'N Q', 'periods': 'Q326', 'bucket': 'EP MD'}))
    except Exception as exc:  # pragma: no cover - CLI demo
        print('GET error:', exc)

    print('\nPOST /api/order')
    try:
        print(post_tod_markets_endpoint('/api/order', 
            {
            "asset_code": "Q-Q127C6X",
            "type": "BUY",
            "price": 10.66,
            "quantity": 10,
            "replace_match": 1,
            "is_persistent": 0,
            "status" : "HOLD"
            }
        ))
    except Exception as exc:  # pragma: no cover - CLI demo
        print('POST error:', exc)
