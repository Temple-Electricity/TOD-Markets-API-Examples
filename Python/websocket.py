#!/usr/bin/env python3
"""
Python helper for TOD Markets WebSocket connection.

Install dependencies:
    pip install websocket-client python-dotenv requests

Usage:
    python Python/websocket.py

This module provides WebSocket connectivity to authenticated private channels
using the Pusher service. It performs a handshake to fetch channel credentials
from the API, then establishes a WebSocket connection.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict

import requests

from api import get_tod_markets_endpoint


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


_ws = _import_websocket_client()
WebSocketApp = _ws.WebSocketApp

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

API_KEY = os.getenv("API_KEY")
DOMAIN_URL = os.getenv("DOMAIN_URL")


class WebSocketManager:
    """Manages WebSocket connection to TOD Markets private channel."""

    def __init__(self):
        self.websocket_details: Dict[str, Any] = {
            "id": None,
            "name": None,
            "channel_key": None,
            "channel_key_expiry": None,
            "pusher_host": None,
            "pusher_key": None,
            "pusher_cluster": None,
        }
        self.ws = None
        self.api_key = API_KEY
        self.domain_url = DOMAIN_URL
        self.channel_name = None

    def set_websocket_details(self, details: Dict[str, Any]) -> None:
        """Update websocket configuration details from API response."""
        self.websocket_details["id"] = details.get("id")
        self.websocket_details["name"] = details.get("name")
        self.websocket_details["channel_key"] = details.get("channel_key")
        self.websocket_details["channel_key_expiry"] = details.get("channel_key_expiry")
        self.websocket_details["pusher_host"] = details.get("pusher_host")
        self.websocket_details["pusher_key"] = details.get("pusher_key")
        self.websocket_details["pusher_cluster"] = details.get("pusher_cluster")

    def get_websocket_details(self) -> None:
        """Fetch websocket configuration from the API."""
        try:
            response = get_tod_markets_endpoint("/api/company")
            data = json.loads(response)
            print("Websocket Details:", json.dumps(data.get("data"), indent=2))
            self.set_websocket_details(data.get("data", {}))
        except Exception as exc:
            print(f"Error fetching websocket details: {exc}")
            raise

    def on_message(self, ws: WebSocketApp, message: str) -> None:
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            event_type = data.get("event")
            event_data = data.get("data", {})

            if event_type == "pusher:connection_established":
                payload = self._parse_event_data(event_data)
                socket_id = payload.get("socket_id") if isinstance(payload, dict) else None
                if socket_id:
                    self.subscribe_private_channel(socket_id)
                return

            if event_type == "pusher:ping":
                self.send_pong()
                return

            event_data = self._parse_event_data(event_data)
            print(f"Received {event_type}: {json.dumps(event_data, indent=2)}")

            # Route to appropriate handler based on event type
            if event_type == "App\\Events\\AssetPriceChangeEventCompany":
                self.handle_price_change(event_data)
            elif event_type == "App\\Events\\OrderUpdated":
                self.handle_order_updated(event_data)
            elif event_type == "App\\Events\\OrderFilled":
                self.handle_order_filled(event_data)
            elif event_type == "App\\Events\\OrderCreated":
                self.handle_order_created(event_data)
            else:
                print(f"Unhandled event type: {event_type}")
        except Exception as exc:
            print(f"Error processing message: {exc}")

    def on_error(self, ws: WebSocketApp, error: Exception) -> None:
        """Handle WebSocket errors."""
        print(f"WebSocket error: {error}")

    def on_close(self, ws: WebSocketApp, close_status_code: int, close_msg: str) -> None:
        """Handle WebSocket closure."""
        print(f"WebSocket closed. Status: {close_status_code}, Message: {close_msg}")

    def on_open(self, ws: WebSocketApp) -> None:
        """Handle WebSocket connection opened."""
        print("WebSocket connection opened")
        self.channel_name = f"private-{self.websocket_details.get('channel_key')}"
        print(f"Preparing to subscribe to channel: {self.channel_name}")

    def _parse_event_data(self, event_data: Any) -> Any:
        """Parse Pusher event data which may be JSON-encoded string."""
        if isinstance(event_data, str):
            try:
                return json.loads(event_data)
            except Exception:
                return event_data
        return event_data

    def _get_base_url(self) -> str:
        """Return base URL for broadcasting auth endpoint."""
        if not self.domain_url:
            raise SystemExit("Missing DOMAIN_URL in environment.")
        base = self.domain_url.rstrip("/")
        if base.endswith("/api"):
            base = base[:-4]
        return base

    def authenticate_channel(self, socket_id: str, channel_name: str) -> Dict[str, Any]:
        """Authenticate private channel subscription via broadcasting auth endpoint."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        payload = {
            "socket_id": socket_id,
            "channel_name": channel_name,
        }
        base = self._get_base_url()
        auth_urls = [
            f"{base}/broadcasting/auth",
            f"{base}/api/broadcasting/auth",
        ]

        last_resp = None
        for auth_url in auth_urls:
            resp = requests.post(auth_url, headers=headers, json=payload, timeout=15)
            last_resp = resp
            if resp.status_code == 403 and auth_url.endswith("/broadcasting/auth"):
                continue
            resp.raise_for_status()
            return resp.json()

        if last_resp is not None:
            last_resp.raise_for_status()
        raise SystemExit("Failed to authenticate Pusher channel.")

    def subscribe_private_channel(self, socket_id: str) -> None:
        """Subscribe to private channel using Pusher protocol."""
        if not self.channel_name:
            self.channel_name = f"private-{self.websocket_details.get('channel_key')}"

        print(f"Authenticating channel: {self.channel_name}")
        auth_payload = self.authenticate_channel(socket_id, self.channel_name)
        subscribe_data = {
            "channel": self.channel_name,
            "auth": auth_payload.get("auth"),
        }
        if "channel_data" in auth_payload:
            subscribe_data["channel_data"] = auth_payload["channel_data"]

        message = {
            "event": "pusher:subscribe",
            "data": subscribe_data,
        }
        print(f"Subscribing to channel: {self.channel_name}")
        self.ws.send(json.dumps(message))

    def send_pong(self) -> None:
        """Respond to Pusher ping events."""
        if self.ws:
            self.ws.send(json.dumps({"event": "pusher:pong", "data": {}}))

    def establish_websocket_connection(self) -> None:
        """Establish WebSocket connection."""
        self.get_websocket_details()

        # Build WebSocket URL
        pusher_key = self.websocket_details.get("pusher_key")
        cluster = self.websocket_details.get("pusher_cluster")
        host = f"ws-{cluster}.pusher.com" if cluster else "ws.pusher.com"

        # Construct WebSocket URL for Pusher
        ws_url = (
            f"wss://{host}/app/{pusher_key}"
            "?protocol=7&client=python&version=1.0&flash=false"
        )
        
        print(f"Connecting to WebSocket: {ws_url}")

        # Create WebSocket app with event handlers
        self.ws = WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        # Run the WebSocket connection (blocking)
        print("Starting WebSocket listener (press Ctrl+C to stop)...")
        try:
            self.ws.run_forever()
        except KeyboardInterrupt:
            print("\nWebSocket listener stopped by user")
            self.ws.close()

    def handle_price_change(self, event_data: Dict[str, Any]) -> None:
        """Handle asset price change events."""
        print(f"[PRICE CHANGE] {event_data}")

    def handle_order_updated(self, event_data: Dict[str, Any]) -> None:
        """Handle order updated events."""
        print(f"[ORDER UPDATED] {event_data}")

    def handle_order_filled(self, event_data: Dict[str, Any]) -> None:
        """Handle order filled events."""
        print(f"[ORDER FILLED] {event_data}")

    def handle_order_created(self, event_data: Dict[str, Any]) -> None:
        """Handle order created events."""
        print(f"[ORDER CREATED] {event_data}")


def establish_websocket_connection() -> None:
    """Main entry point for establishing WebSocket connection."""
    manager = WebSocketManager()
    try:
        manager.establish_websocket_connection()
    except Exception as exc:
        print(f"Failed to establish WebSocket connection: {exc}")
        raise


if __name__ == "__main__":
    establish_websocket_connection()
