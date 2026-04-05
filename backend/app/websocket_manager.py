from typing import Dict, Set
import asyncio
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, game_id: int, websocket: WebSocket):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = set()
        self.active_connections[game_id].add(websocket)
    
    def disconnect(self, game_id: int, websocket: WebSocket):
        if game_id in self.active_connections:
            self.active_connections[game_id].discard(websocket)
            if len(self.active_connections[game_id]) == 0:
                del self.active_connections[game_id]
    
    async def broadcast_to_game(self, game_id: int, message: dict):
        if game_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[game_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.add(connection)
            
            for connection in disconnected:
                self.disconnect(game_id, connection)

manager = ConnectionManager()