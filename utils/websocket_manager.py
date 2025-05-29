from fastapi import WebSocket
from typing import Dict, List
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, topic: str = None):
        await websocket.accept()
        if topic:
            self.active_connections[topic].append(websocket)
        else:
            # fallback for backward compatibility (non-topic specific)
            self.active_connections["default"].append(websocket)

    def disconnect(self, websocket: WebSocket, topic: str = None):
        if topic and websocket in self.active_connections[topic]:
            self.active_connections[topic].remove(websocket)
        else:
            # remove from all topics just in case
            for conns in self.active_connections.values():
                if websocket in conns:
                    conns.remove(websocket)

    async def broadcast(self, topic: str, message: dict):
        if topic in self.active_connections:
            for connection in self.active_connections[topic]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Failed to send message: {e}")


manager = ConnectionManager()