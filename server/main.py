from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
from typing import Dict, List, Optional
import json
from fastapi.responses import FileResponse
import os
from .database.models import get_db, Pack, init_db
from .database.seed import seed_test_pack
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException

init_db()
# Always seed test pack on startup (seed logic is idempotent)
seed_test_pack()

app = FastAPI(title="Retro Online", description="Backend MVP for Retro Online R36S", version="1.0.0")

class UserState(BaseModel):
    username: str
    status: str
    game: Optional[str] = None
    room_id: Optional[str] = None

class ConnectionManager:
    def __init__(self):
        # Maps websocket to username
        self.active_connections: Dict[WebSocket, str] = {}
        # Maps username to UserState
        self.user_states: Dict[str, UserState] = {}
        # Simple rooms: mapping room_id to dictionary of room data
        self.rooms: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[websocket] = username
        self.user_states[username] = UserState(username=username, status="Online")
        await self.broadcast_states()

    def disconnect(self, websocket: WebSocket):
        username = self.active_connections.get(websocket)
        if username:
            del self.active_connections[websocket]
            if username in self.user_states:
                del self.user_states[username]
            # Optionally remove from rooms if needed

    async def broadcast(self, message: str):
        for connection in self.active_connections.keys():
            try:
                await connection.send_text(message)
            except Exception:
                pass

    async def broadcast_states(self):
        states = [state.model_dump() for state in self.user_states.values()]
        await self.broadcast(json.dumps({"type": "states", "data": states}))

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"message": "Retro Online Backend MVP is running"}

@app.get("/packs")
def list_packs(db: Session = Depends(get_db)):
    packs = db.query(Pack).all()
    return packs

@app.get("/packs/download/{pack_id}/{file_type}")
def download_pack_file(pack_id: int, file_type: str, db: Session = Depends(get_db)):
    pack = db.query(Pack).filter(Pack.id == pack_id).first()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    # Dynamic folder mapping based on game name
    # e.g. "Mario Kart" -> "mario_kart"
    folder_name = pack.game.lower().replace(" ", "_")
    base_folder = os.path.join("server/packs_storage", folder_name)

    if file_type == "rom":
        file_path = os.path.join(base_folder, pack.rom_filename)
    elif file_type == "core":
        file_path = os.path.join(base_folder, pack.core_filename)
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(path=file_path, filename=os.path.basename(file_path))

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    try:
        while True:
            data = await websocket.receive_text()
            # Simple message parsing
            try:
                msg = json.loads(data)
                action = msg.get("action")

                if action == "update_status":
                    status = msg.get("status")
                    if status and username in manager.user_states:
                        manager.user_states[username].status = status
                        manager.user_states[username].game = msg.get("game")
                        await manager.broadcast_states()

                elif action == "create_room":
                    room_id = msg.get("room_id")
                    game = msg.get("game")
                    if room_id:
                        manager.rooms[room_id] = {
                            "host": username,
                            "game": game,
                            "players": [username],
                            "status": "Waiting"
                        }
                        manager.user_states[username].room_id = room_id
                        await websocket.send_text(json.dumps({"type": "room_created", "room_id": room_id}))
                        await manager.broadcast_states()

                elif action == "join_room":
                    room_id = msg.get("room_id")
                    if room_id in manager.rooms:
                        manager.rooms[room_id]["players"].append(username)
                        manager.user_states[username].room_id = room_id
                        await websocket.send_text(json.dumps({"type": "room_joined", "room_id": room_id}))
                        await manager.broadcast_states()

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast_states()

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
