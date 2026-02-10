import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
from starlette.websockets import WebSocket

log = structlog.get_logger()


@dataclass
class AgentConnection:
    agent_id: uuid.UUID
    websocket: WebSocket
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, AgentConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            # Close existing connection if any
            existing = self._connections.get(agent_id)
            if existing is not None:
                try:
                    await existing.websocket.close(code=1000, reason="Replaced by new connection")
                except Exception:
                    pass
            self._connections[agent_id] = AgentConnection(
                agent_id=agent_id, websocket=websocket
            )
            log.info("agent_connected", agent_id=str(agent_id))

    async def remove(self, agent_id: uuid.UUID) -> None:
        async with self._lock:
            self._connections.pop(agent_id, None)
            log.info("agent_disconnected", agent_id=str(agent_id))

    def is_connected(self, agent_id: uuid.UUID) -> bool:
        return agent_id in self._connections

    async def send(self, agent_id: uuid.UUID, data: dict) -> bool:
        conn = self._connections.get(agent_id)
        if conn is None:
            return False
        try:
            await conn.websocket.send_json(data)
            return True
        except Exception as e:
            log.error("send_failed", agent_id=str(agent_id), error=str(e))
            await self.remove(agent_id)
            return False

    def update_heartbeat(self, agent_id: uuid.UUID) -> None:
        conn = self._connections.get(agent_id)
        if conn:
            conn.last_heartbeat = datetime.now(timezone.utc)

    def get_connection(self, agent_id: uuid.UUID) -> AgentConnection | None:
        return self._connections.get(agent_id)


# Singleton instance
connection_manager = ConnectionManager()
