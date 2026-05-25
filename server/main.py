from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
from typing import Dict, List, Optional
import json
from fastapi.responses import FileResponse
import os
from .database.models import get_db, Pack, User, init_db, SessionLocal
from .database.seed import seed_test_pack
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from pydantic import BaseModel
import hashlib

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

    def get_pack_by_id(self, pack_id: int):
        with SessionLocal() as db:
            return db.query(Pack).filter(Pack.id == pack_id).first()

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[websocket] = username
        self.user_states[username] = UserState(username=username, status="Online")
        await self.broadcast_states()

    async def disconnect(self, websocket: WebSocket):
        username = self.active_connections.get(websocket)
        if username:
            del self.active_connections[websocket]

            state = self.user_states.get(username)
            if state:
                room_id = state.room_id
                if room_id and room_id in self.rooms:
                    room = self.rooms[room_id]
                    if username in room["players"]:
                        del room["players"][username]
                        # Clean up room if empty
                        if not room["players"]:
                            del self.rooms[room_id]
                        else:
                            # If host left, maybe reassign or abandon, but for MVP just clean player
                            pass
                del self.user_states[username]

    async def broadcast(self, message: str):
        # Iterate over a list copy to prevent RuntimeError if dictionary changes during await
        for connection in list(self.active_connections.keys()):
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

class UserAuth(BaseModel):
    username: str
    password: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.post("/auth/register")
def register(user_data: UserAuth, db: Session = Depends(get_db)):
    if not user_data.username or not user_data.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password)
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/auth/login")
def login(user_data: UserAuth, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or user.password_hash != hash_password(user_data.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"message": "Login successful"}

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
                    pack_id = msg.get("pack_id")
                    if room_id and pack_id:
                        try:
                            pack_id_int = int(pack_id)
                        except ValueError:
                            await websocket.send_text(json.dumps({"type": "error", "message": "Invalid pack_id"}))
                            continue

                        pack = manager.get_pack_by_id(pack_id_int)
                        if pack:
                            manager.rooms[room_id] = {
                                "host": username,
                                "game": pack.game,
                                "pack_id": pack.id,
                                "max_players": pack.max_players,
                                "players": {username: {"ready": False}},
                                "status": "Waiting"
                            }
                            manager.user_states[username].room_id = room_id
                            await websocket.send_text(json.dumps({"type": "room_created", "room_id": room_id}))
                            await manager.broadcast_states()
                        else:
                            await websocket.send_text(json.dumps({"type": "error", "message": "Pack not found"}))

                elif action == "join_room":
                    room_id = msg.get("room_id")
                    if room_id in manager.rooms:
                        room = manager.rooms[room_id]
                        if len(room["players"]) < room["max_players"]:
                            room["players"][username] = {"ready": False}
                            manager.user_states[username].room_id = room_id
                            await websocket.send_text(json.dumps({"type": "room_joined", "room_id": room_id}))
                            await manager.broadcast_states()
                        else:
                            await websocket.send_text(json.dumps({"type": "error", "message": "Room is full"}))
                    else:
                        await websocket.send_text(json.dumps({"type": "error", "message": "Room not found"}))

                elif action == "ready":
                    room_id = manager.user_states.get(username, UserState(username=username, status="")).room_id
                    if room_id and room_id in manager.rooms:
                        room = manager.rooms[room_id]
                        if username in room["players"]:
                            room["players"][username]["ready"] = True
                            await websocket.send_text(json.dumps({"type": "system", "message": "You are marked as READY"}))

                            # Check if everyone is ready
                            all_ready = all(p_data["ready"] for p_data in room["players"].values())
                            if all_ready and len(room["players"]) > 1: # Require at least 2 players to auto-start for MVP
                                room["status"] = "Playing"
                                # Broadcast game start to everyone in the room
                                start_msg = json.dumps({
                                    "type": "game_start",
                                    "room_id": room_id,
                                    "pack_id": room["pack_id"],
                                    "host": room["host"]
                                })
                                # Iterate over a list copy to prevent RuntimeError
                                for ws, un in list(manager.active_connections.items()):
                                    if un in room["players"]:
                                        await ws.send_text(start_msg)

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        await manager.broadcast_states()

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
