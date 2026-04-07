from typing import Dict, Set, List, Optional
import asyncio
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Connexions par partie : {game_id: {websocket, ...}}
        # On stocke juste les websockets, pas des dicts
        self.game_connections: Dict[int, Set[WebSocket]] = {}
        
        # Mapping pour associer un user_id à un game_id (pour savoir dans quelle partie est l'utilisateur)
        self.user_game_map: Dict[int, int] = {}
        
        # Connexions personnelles par user : {user_id: {websocket, ...}}
        self.user_connections: Dict[int, Set[WebSocket]] = {}

    # ──────────────────────────────────────────────
    # Connexions de partie
    # ──────────────────────────────────────────────

    async def connect(self, game_id: int, websocket: WebSocket, user_id: int | None = None):
        await websocket.accept()

        if game_id not in self.game_connections:
            self.game_connections[game_id] = set()
        
        # Ajouter le websocket à la partie
        self.game_connections[game_id].add(websocket)

        # Enregistrer la relation user -> game
        if user_id:
            self.user_game_map[user_id] = game_id
            self._register_user(user_id, websocket)

        logger.info(
            f"WS connecté — game={game_id}, user={user_id}, "
            f"total connexions partie: {len(self.game_connections[game_id])}"
        )

    def disconnect(self, game_id: int, websocket: WebSocket, user_id: int | None = None):
        if game_id in self.game_connections:
            self.game_connections[game_id].discard(websocket)
            if not self.game_connections[game_id]:
                del self.game_connections[game_id]

        if user_id:
            # Supprimer la relation user -> game
            if user_id in self.user_game_map:
                del self.user_game_map[user_id]
            self._unregister_user(user_id, websocket)

        logger.info(f"WS déconnecté — game={game_id}, user={user_id}")

    # ──────────────────────────────────────────────
    # Connexions personnelles (canal user)
    # ──────────────────────────────────────────────

    def _register_user(self, user_id: int, websocket: WebSocket):
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)

    def _unregister_user(self, user_id: int, websocket: WebSocket):
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    # ──────────────────────────────────────────────
    # Envois
    # ──────────────────────────────────────────────

    async def broadcast_to_game(self, game_id: int, message: dict):
        """Envoie un message à tous les WebSockets d'une partie."""
        if game_id not in self.game_connections:
            return

        dead = set()
        for ws in self.game_connections[game_id].copy():
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Broadcast game {game_id} échoué: {e}")
                dead.add(ws)

        for ws in dead:
            self.game_connections[game_id].discard(ws)

    async def send_to_user(self, user_id: int, message: dict):
        """
        Envoie un message directement à un utilisateur spécifique
        sur tous ses WebSockets actifs (multi-onglets, reconnexion, etc.).
        """
        if user_id not in self.user_connections:
            logger.debug(f"Pas de WS actif pour user {user_id}")
            return False

        dead = set()
        success = False
        for ws in self.user_connections[user_id].copy():
            try:
                await ws.send_json(message)
                success = True
            except Exception as e:
                logger.warning(f"send_to_user {user_id} échoué: {e}")
                dead.add(ws)

        for ws in dead:
            self._unregister_user(user_id, ws)
        
        return success

    async def send_to_user_in_game(self, game_id: int, user_id: int, message: dict):
        """
        Envoie un message à un utilisateur spécifique dans une partie.
        """
        # Méthode 1: utiliser le mapping user -> game
        if user_id in self.user_game_map and self.user_game_map[user_id] == game_id:
            if user_id in self.user_connections:
                for ws in self.user_connections[user_id]:
                    try:
                        await ws.send_json(message)
                        logger.info(f"✅ Message envoyé à user {user_id} dans game {game_id}")
                        return True
                    except Exception as e:
                        logger.error(f"Erreur envoi à user {user_id}: {e}")
        
        # Méthode 2: broadcast classique (fallback)
        if game_id in self.game_connections:
            for ws in self.game_connections[game_id]:
                try:
                    await ws.send_json(message)
                except:
                    pass
        
        return False

    async def broadcast_to_all(self, message: dict):
        """Broadcast global — toutes les parties."""
        for game_id in list(self.game_connections.keys()):
            await self.broadcast_to_game(game_id, message)

    def get_game_connection_count(self, game_id: int) -> int:
        return len(self.game_connections.get(game_id, set()))

    def get_user_connection_count(self, user_id: int) -> int:
        return len(self.user_connections.get(user_id, set()))

    def is_user_online(self, user_id: int) -> bool:
        return user_id in self.user_connections and bool(self.user_connections[user_id])
    
    def get_user_game(self, user_id: int) -> Optional[int]:
        """Retourne l'ID de la partie à laquelle l'utilisateur est connecté"""
        return self.user_game_map.get(user_id)


manager = ConnectionManager()
