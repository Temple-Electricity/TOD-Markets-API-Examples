#!/usr/bin/env python3
"""
Python example for the TOD Markets private WebSocket connection.

Install dependencies:
    pip install websocket-client python-dotenv requests

Usage:
    python Python/websocket.py

TOD Markets publishes live updates through one of two services that both speak the Pusher protocol:
its own WebSocket server (Laravel Reverb, the primary) or Pusher (the fallback). GET /api/company names
the active one in `broadcast_driver`, so this script reads it before every connection and reconnects
whenever it changes.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Tuple
from urllib.parse import urlparse

import requests

from api import API_KEY, DOMAIN_URL, get_tod_markets_endpoint


def _import_websocket_client():
    """Import websocket-client without shadowing by this file name."""
    script_dir = os.path.abspath(os.path.dirname(__file__))
    removed = False
    if sys.path and os.path.abspath(sys.path[0]) == script_dir:
        sys.path.pop(0)
        removed = True
    try:
        import websocket as ws  # websocket-client
    except Exception as exc:  # pragma: no cover - dependency error
        raise SystemExit(
            "Missing or incompatible dependency 'websocket-client'. "
            "Run: python -m pip install --user websocket-client"
        ) from exc
    finally:
        if removed:
            sys.path.insert(0, script_dir)
    return ws


WebSocketApp = _import_websocket_client().WebSocketApp

_platform = urlparse(DOMAIN_URL)
PLATFORM_URL = f"{_platform.scheme}://{_platform.netloc}"

CLIENT_NAME = "tod-markets-python-example"
CLIENT_VERSION = "2.0"
SERVICE_CHECK_INTERVAL_SECONDS = 5 * 60
RECONNECT_DELAY_SECONDS = 5


def get_connection_details() -> Dict[str, Any]:
    """Fetch the company's channel and WebSocket connection details from GET /api/company."""
    return json.loads(get_tod_markets_endpoint("/api/company"))["data"]


def endpoint_for(details: Dict[str, Any]) -> Tuple[str, str]:
    """Return (service, url) for the service named by `broadcast_driver`.

    Reverb is used whenever the API names it. Pusher is used when the API names it, and also when the
    field is absent, which is how a platform release from before Reverb answers.
    """
    query = f"protocol=7&client={CLIENT_NAME}&version={CLIENT_VERSION}"

    if details.get("broadcast_driver") == "reverb":
        scheme = "wss" if details.get("reverb_use_tls") else "ws"
        url = f"{scheme}://{details['reverb_host']}:{details['reverb_port']}/app/{details['reverb_key']}?{query}"
        return "reverb", url

    url = f"wss://ws-{details['pusher_cluster']}.pusher.com:443/app/{details['pusher_key']}?{query}"
    return "pusher", url


def authorise_channel(socket_id: str, channel_name: str) -> Dict[str, Any]:
    """Ask the platform to authorise this socket to join a private channel."""
    response = requests.post(
        f"{PLATFORM_URL}/api/broadcasting/auth",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json",
        },
        json={"socket_id": socket_id, "channel_name": channel_name},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _parse_event_data(event_data: Any) -> Any:
    """Parse a Pusher protocol `data` field, which arrives as a JSON-encoded string."""
    if isinstance(event_data, str):
        try:
            return json.loads(event_data)
        except ValueError:
            return event_data
    return event_data


class WebSocketManager:
    """Keeps a connection open to whichever service TOD Markets names, reconnecting when it changes."""

    def __init__(self) -> None:
        self.ws: WebSocketApp | None = None
        self.service: str | None = None
        self.channel_name: str | None = None
        self.event_handlers: Dict[str, Callable[[Any], None]] = {
            "App\\Events\\AssetPriceChangeEventCompany": self.handle_price_change,
            "App\\Events\\OrderCreated": self.handle_order_created,
            "App\\Events\\OrderUpdated": self.handle_order_updated,
            "App\\Events\\OrderFilled": self.handle_order_filled,
        }

    def on_message(self, ws: WebSocketApp, message: str) -> None:
        """Handle the Pusher protocol messages, then route channel events to their handlers."""
        payload = json.loads(message)
        event = payload.get("event")
        data = _parse_event_data(payload.get("data"))

        if event == "pusher:connection_established":
            print(f"Connected with socket id {data['socket_id']}; subscribing to {self.channel_name}")
            self.subscribe(data["socket_id"])
            return

        if event == "pusher:ping":
            self.send("pusher:pong")
            return

        if event == "pusher:pong":
            return

        if event == "pusher_internal:subscription_succeeded":
            print(f"Subscribed to {payload.get('channel')}")
            return

        if event == "pusher:error":
            code = data.get("code") if isinstance(data, dict) else None
            text = data.get("message") if isinstance(data, dict) else data
            print(f"Server error{f' {code}' if code else ''}: {text}")
            return

        handler = self.event_handlers.get(event)
        if handler:
            handler(data)
        else:
            print(f"Unhandled event {event}: {json.dumps(data, indent=2)}")

    def on_error(self, ws: WebSocketApp, error: Exception) -> None:
        """Handle WebSocket errors."""
        print(f"WebSocket error: {error}")

    def on_close(self, ws: WebSocketApp, close_status_code: int | None, close_msg: str | None) -> None:
        """Handle WebSocket closure."""
        print(f"WebSocket closed ({close_status_code}) {close_msg or ''}")

    def send(self, event: str, data: Dict[str, Any] | None = None) -> None:
        """Send a Pusher protocol message."""
        if self.ws:
            self.ws.send(json.dumps({"event": event, "data": data or {}}))

    def subscribe(self, socket_id: str) -> None:
        """Authorise the private company channel and subscribe to it."""
        try:
            auth = authorise_channel(socket_id, self.channel_name)
        except requests.RequestException as exc:
            print(f"Channel authorisation failed: {exc}")
            self.ws.close()
            return

        self.send("pusher:subscribe", {"channel": self.channel_name, **auth})

    def watch_connection_details(self, stop: threading.Event) -> None:
        """Re-read /api/company periodically and close the socket if the service or channel has changed."""
        while not stop.wait(SERVICE_CHECK_INTERVAL_SECONDS):
            try:
                latest = get_connection_details()
            except Exception as exc:
                print(f"Could not re-check connection details: {exc}")
                continue

            service, _ = endpoint_for(latest)
            channel_name = f"private-{latest['channel_key']}"
            if service != self.service or channel_name != self.channel_name:
                print(f"Connection details changed (now {service}); reconnecting.")
                self.ws.close()
                return

    def connect_once(self) -> None:
        """Open one connection to the active service and block until it closes."""
        details = get_connection_details()
        self.service, url = endpoint_for(details)
        self.channel_name = f"private-{details['channel_key']}"

        print(f"Connecting to {self.service}: {url}")
        self.ws = WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        stop = threading.Event()
        watcher = threading.Thread(target=self.watch_connection_details, args=(stop,), daemon=True)
        watcher.start()
        try:
            # Reverb checks the Origin header against the platform's allowed origins, so send the platform's own address.
            self.ws.run_forever(origin=PLATFORM_URL, ping_interval=60, ping_timeout=30)
        finally:
            stop.set()

    def run(self) -> None:
        """Keep a connection open, reconnecting after a drop or a change of service."""
        while True:
            try:
                self.connect_once()
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"Connection attempt failed: {exc}")

            print(f"Reconnecting in {RECONNECT_DELAY_SECONDS}s...")
            time.sleep(RECONNECT_DELAY_SECONDS)

    def handle_price_change(self, event_data: Dict[str, Any]) -> None:
        """Handle asset price change events."""
        print(f"[PRICE CHANGE] {event_data}")

    def handle_order_created(self, event_data: Dict[str, Any]) -> None:
        """Handle order created events."""
        print(f"[ORDER CREATED] {event_data}")

    def handle_order_updated(self, event_data: Dict[str, Any]) -> None:
        """Handle order updated events."""
        print(f"[ORDER UPDATED] {event_data}")

    def handle_order_filled(self, event_data: Dict[str, Any]) -> None:
        """Handle order filled events."""
        print(f"[ORDER FILLED] {event_data}")


def establish_websocket_connection() -> None:
    """Main entry point for establishing WebSocket connection."""
    try:
        WebSocketManager().run()
    except KeyboardInterrupt:
        print("\nWebSocket listener stopped by user")


if __name__ == "__main__":
    establish_websocket_connection()
