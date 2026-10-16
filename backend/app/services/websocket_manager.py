"""SkillProof - WebSocket Connection & Broadcast Manager.

Enables real-time bi-directional synchronization between the FastAPI server
and connected web clients (students, mentors, recruiters).
"""
import asyncio
import json
import logging
from typing import Dict, Any, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time events."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")
        
        # Send initial connection acknowledgment
        await self.send_personal_message(
            {
                "type": "connection_established",
                "message": "Connected to SkillProof Real-Time Sync Engine",
                "active_clients": len(self.active_connections),
            },
            websocket,
        )

    async def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a JSON message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal WebSocket message: {e}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        async with self._lock:
            dead_connections = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.debug(f"Client disconnected during broadcast: {e}")
                    dead_connections.append(connection)

            for dead in dead_connections:
                if dead in self.active_connections:
                    self.active_connections.remove(dead)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# Singleton connection manager instance
manager = ConnectionManager()
