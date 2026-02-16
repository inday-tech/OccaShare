from typing import List, Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # active_connections maps client_id to WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast_to_client(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception:
                pass

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be dead, handled by disconnect
                pass

manager = ConnectionManager()
