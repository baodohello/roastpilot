"""Artisan WebSocket device server.

Artisan attaches to RoastPilot as a WebSocket *device*. In this exchange Artisan
is always the client: it connects to `ws://<host>:<port>/<path>` and sends a
data request every sampling interval, e.g.

    {"command": "getData", "id": 44683, "machine": 0}

RoastPilot answers with the current temperatures under a data node:

    {"id": 44683, "data": {"BT": 189.2, "ET": 220.5}}

All node names (message id, data, BT, ET) are configurable in Artisan's
WebSocket tab; pass matching names here. RoastPilot can also push messages to
Artisan (CHARGE/DROP/events) via broadcast().

See https://artisan-scope.org/devices/websockets/ for the full protocol.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable

from websockets.sync.server import serve

Provider = Callable[[], float | None]


class ArtisanWebSocketDevice:
    """A WebSocket server that serves BT/ET readings to Artisan."""

    def __init__(
        self,
        bt_provider: Provider | None = None,
        et_provider: Provider | None = None,
        host: str = "127.0.0.1",
        port: int = 8080,
        path: str = "/",
        *,
        message_id_node: str = "id",
        data_node: str = "data",
        bt_node: str = "BT",
        et_node: str = "ET",
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.message_id_node = message_id_node
        self.data_node = data_node
        self.bt_node = bt_node
        self.et_node = et_node
        self._bt_provider = bt_provider or (lambda: None)
        self._et_provider = et_provider or (lambda: None)
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._send_lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------------
    @property
    def bound_port(self) -> int:
        if self._server is None:
            return self.port
        return int(self._server.socket.getsockname()[1])

    @property
    def connection_count(self) -> int:
        if self._server is None:
            return 0
        return len(self._server.connections)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        def handler(connection: Any) -> None:
            request = getattr(connection, "request", None)
            if self.path and request is not None and request.path != self.path:
                try:
                    connection.close(code=1008, reason="path not found")
                except Exception:
                    pass
                return
            try:
                for message in connection:
                    response = self._on_message(message)
                    if response is not None:
                        with self._send_lock:
                            connection.send(response)
            except Exception:
                pass

        self._server = serve(handler, self.host, self.port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    # -- outbound push ------------------------------------------------------
    def broadcast(self, message: dict[str, Any]) -> None:
        """Push a message (e.g. ``{"Message": "CHARGE"}``) to connected clients."""
        if self._server is None:
            return
        text = json.dumps(message)
        for connection in list(self._server.connections):
            try:
                with self._send_lock:
                    connection.send(text)
            except Exception:
                pass

    # -- inbound requests ---------------------------------------------------
    def _on_message(self, raw: str | bytes) -> str | None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(message, dict):
            return None
        response: dict[str, Any] = {}
        message_id = message.get(self.message_id_node)
        if message_id is not None:
            response[self.message_id_node] = message_id
        data: dict[str, Any] = {}
        bt = self._bt_provider()
        if bt is not None:
            data[self.bt_node] = bt
        et = self._et_provider()
        if et is not None:
            data[self.et_node] = et
        response[self.data_node] = data
        return json.dumps(response)
