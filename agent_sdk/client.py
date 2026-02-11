import asyncio
import json
import signal
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import structlog
import websockets
from websockets.asyncio.client import ClientConnection

log = structlog.get_logger()

RequestHandler = Callable[[str, dict[str, Any], str], Awaitable[dict[str, Any]]]


class ClawciergeAgent:
    def __init__(self, platform_url: str | None = None, api_key: str | None = None) -> None:
        self._handler: RequestHandler | None = None
        self._ws: ClientConnection | None = None
        self._running = False
        self._platform_url = platform_url.rstrip("/") if platform_url else None
        self._api_key = api_key

    def on_request(self, handler: RequestHandler) -> None:
        """Register a handler for incoming requests.

        Handler signature: async def handler(action: str, params: dict, sender_id: str) -> dict
        """
        self._handler = handler

    async def connect(self, url: str, api_key: str) -> None:
        """Connect to the platform with reconnection logic."""
        self._running = True

        # Handle graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.disconnect()))

        backoff = 1.0
        while self._running:
            try:
                separator = "&" if "?" in url else "?"
                ws_url = f"{url}{separator}token={api_key}"
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    backoff = 1.0
                    log.info("connected", url=url)

                    # Start heartbeat task
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    try:
                        await self._message_loop(ws)
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass

            except websockets.exceptions.ConnectionClosed:
                log.info("connection_closed")
            except Exception as e:
                log.error("connection_error", error=str(e))

            if self._running:
                log.info("reconnecting", backoff=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            if self._ws:
                try:
                    await self._ws.send(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break

    async def _message_loop(self, ws: ClientConnection) -> None:
        async for raw_message in ws:
            try:
                data = json.loads(raw_message)
                msg_type = data.get("type")

                if msg_type == "request.received":
                    await self._handle_request(ws, data)
                elif msg_type == "ping":
                    await ws.send(json.dumps({"type": "heartbeat"}))

            except Exception as e:
                log.error("message_error", error=str(e))

    async def _handle_request(self, ws: ClientConnection, data: dict) -> None:
        request_id = data["request_id"]
        action = data["action"]
        params = data.get("params", {})
        sender_id = data.get("sender_id", "")

        # Send ack
        await ws.send(json.dumps({"type": "ack", "request_id": request_id}))

        if self._handler is None:
            await ws.send(
                json.dumps(
                    {
                        "type": "action.result",
                        "request_id": request_id,
                        "status": "error",
                        "error": "No handler registered",
                    }
                )
            )
            return

        try:
            result = await self._handler(action, params, sender_id)
            await ws.send(
                json.dumps(
                    {
                        "type": "action.result",
                        "request_id": request_id,
                        "status": "completed",
                        "result": result,
                    }
                )
            )
        except Exception as e:
            await ws.send(
                json.dumps(
                    {
                        "type": "action.result",
                        "request_id": request_id,
                        "status": "error",
                        "error": str(e),
                    }
                )
            )

    # --- HTTP client methods for agent-to-agent communication ---

    def _ensure_http_config(self) -> None:
        if not self._platform_url or not self._api_key:
            raise RuntimeError(
                "platform_url and api_key must be set to use HTTP methods. "
                "Pass them to ClawciergeAgent(platform_url=..., api_key=...)"
            )

    async def resolve(self, handle: str) -> dict[str, Any]:
        """Look up another agent by handle. Returns agent metadata and capabilities."""
        self._ensure_http_config()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._platform_url}/v1/directory/{handle}",
            )
            resp.raise_for_status()
            return resp.json()

    async def send_request(
        self, handle: str, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a request to another agent by handle. Returns the request receipt (id, status)."""
        self._ensure_http_config()
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._platform_url}/v1/agents/{handle}/requests",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"action": action, "params": params or {}},
            )
            resp.raise_for_status()
            return resp.json()

    async def poll_request(self, request_id: str) -> dict[str, Any]:
        """Poll for the status/result of a previously sent request."""
        self._ensure_http_config()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._platform_url}/v1/requests/{request_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return resp.json()
