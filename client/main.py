import asyncio
import websockets
import json
import sys
from .sync.manager import SyncManager
from .launcher.retroarch import RetroArchLauncher

class RetroClient:
    def __init__(self, username, server_url="https://yukito2-production.up.railway.app"):
        self.username = username

        # Determine HTTP and WS URLs based on provided base URL
        self.server_http = server_url.rstrip("/")
        if self.server_http.startswith("https://"):
            ws_base = self.server_http.replace("https://", "wss://")
        elif self.server_http.startswith("http://"):
            ws_base = self.server_http.replace("http://", "ws://")
        else:
            # Fallback if no scheme provided
            self.server_http = f"http://{server_url}"
            ws_base = f"ws://{server_url}"

        self.server_ws = f"{ws_base}/ws/{username}"
        self.websocket = None
        self.is_connected = False
        self.sync_manager = SyncManager(backend_url=self.server_http)
        self.launcher = RetroArchLauncher()

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.server_ws)
            self.is_connected = True
            print(f"Connected to Retro Online WebSockets as {self.username}")
            # Start listening task
            asyncio.create_task(self.listen())
        except Exception as e:
            print(f"WebSocket connection failed ({e}). Social features (rooms/status) won't work.")
            print(f"However, HTTP features (packs, sync, launch) are still available via {self.server_http}.")

    async def listen(self):
        try:
            while self.is_connected and self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                self.handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            print("Connection to server closed.")
            self.is_connected = False

    def handle_message(self, data):
        msg_type = data.get("type")
        if msg_type == "states":
            print("\n--- Users Online ---")
            for user in data.get("data", []):
                game_info = f" playing {user.get('game')}" if user.get('game') else ""
                room_info = f" in room {user.get('room_id')}" if user.get('room_id') else ""
                print(f"● {user['username']} - {user['status']}{game_info}{room_info}")
            print("--------------------\n")
            print("> ", end="", flush=True)
        elif msg_type == "room_created":
            print(f"\nRoom created successfully: {data.get('room_id')}")
            print("> ", end="", flush=True)
        elif msg_type == "room_joined":
            print(f"\nJoined room successfully: {data.get('room_id')}")
            print("> ", end="", flush=True)
        elif msg_type == "system" or msg_type == "error":
            print(f"\n[{msg_type.upper()}] {data.get('message')}")
            print("> ", end="", flush=True)
        elif msg_type == "game_start":
            print(f"\n[SYSTEM] All players ready! Starting game...")
            pack_id = data.get("pack_id")
            host = data.get("host")
            is_host = (self.username == host)
            connect_ip = "127.0.0.1" if not is_host else None # In a real scenario, use actual IP of the host
            # Use create_task to avoid blocking the listen() event loop
            asyncio.create_task(self._auto_launch_async(pack_id, is_host, connect_ip))
            print("> ", end="", flush=True)

    async def _auto_launch_async(self, pack_id, is_host, connect_ip):
        packs = await asyncio.to_thread(self.sync_manager.fetch_packs)
        pack = next((p for p in packs if p['id'] == pack_id), None)
        if pack:
            rom_path = f"client/roms/{pack['rom_filename']}"
            core_path = f"client/cores/{pack['core_filename']}"
            self.launcher.launch(core_path, rom_path, is_host=is_host, connect_ip=connect_ip)
        else:
            print("\nFailed to auto-launch: Pack not found.")
            print("> ", end="", flush=True)

    async def update_status(self, status, game=None):
        if self.is_connected:
            msg = {"action": "update_status", "status": status, "game": game}
            await self.websocket.send(json.dumps(msg))

    async def create_room(self, room_id, pack_id):
        if self.is_connected:
            msg = {"action": "create_room", "room_id": room_id, "pack_id": pack_id}
            await self.websocket.send(json.dumps(msg))

    async def join_room(self, room_id):
        if self.is_connected:
            msg = {"action": "join_room", "room_id": room_id}
            await self.websocket.send(json.dumps(msg))

    async def set_ready(self):
        if self.is_connected:
            msg = {"action": "ready"}
            await self.websocket.send(json.dumps(msg))

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False

async def main():
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("Enter username: ")

    client = RetroClient(username)
    # Attempt to connect to WebSockets, but don't exit if it fails
    await client.connect()

    # Simple interactive CLI
    while True:
        try:
            # Using asyncio.to_thread to not block the event loop with input()
            cmd = await asyncio.to_thread(input, "> ")
            parts = cmd.strip().split(" ")

            if not parts or not parts[0]:
                continue
            command = parts[0].lower()

            if command == "quit":
                await client.disconnect()
                break
            elif command == "status":
                if client.is_connected:
                    status = " ".join(parts[1:]) if len(parts) > 1 else "Online"
                    await client.update_status(status)
                else:
                    print("Error: WebSocket is not connected.")
            elif command == "play":
                if client.is_connected:
                    game = " ".join(parts[1:]) if len(parts) > 1 else "Unknown Game"
                    await client.update_status("En partida", game)
                else:
                    print("Error: WebSocket is not connected.")
            elif command == "create":
                if client.is_connected:
                    if len(parts) > 2:
                        room_id = parts[1]
                        pack_id = parts[2]
                        await client.create_room(room_id, pack_id)
                    else:
                        print("Usage: create <room_id> <pack_id>")
                else:
                    print("Error: WebSocket is not connected.")
            elif command == "join":
                if client.is_connected:
                    if len(parts) > 1:
                        room_id = parts[1]
                        await client.join_room(room_id)
                    else:
                        print("Usage: join <room_id>")
                else:
                    print("Error: WebSocket is not connected.")
            elif command == "ready":
                if client.is_connected:
                    await client.set_ready()
                else:
                    print("Error: WebSocket is not connected.")
            elif command == "packs":
                packs = await asyncio.to_thread(client.sync_manager.fetch_packs)
                if not packs:
                    print("No packs found.")
                for p in packs:
                    print(f"[{p['id']}] {p['game']} ({p['system']})")
            elif command == "sync":
                if len(parts) > 1:
                    pack_id = int(parts[1])
                    packs = await asyncio.to_thread(client.sync_manager.fetch_packs)
                    pack = next((p for p in packs if p['id'] == pack_id), None)
                    if pack:
                        await asyncio.to_thread(client.sync_manager.sync_pack, pack['id'], pack['rom_filename'], pack['core_filename'])
                    else:
                        print(f"Pack {pack_id} not found.")
                else:
                    print("Usage: sync <pack_id>")
            elif command == "launch":
                if len(parts) > 1:
                    pack_id = int(parts[1])
                    is_host = "--host" in parts
                    connect_ip = None
                    for i, p in enumerate(parts):
                        if p == "--connect" and i + 1 < len(parts):
                            connect_ip = parts[i+1]

                    packs = await asyncio.to_thread(client.sync_manager.fetch_packs)
                    pack = next((p for p in packs if p['id'] == pack_id), None)
                    if pack:
                        rom_path = f"client/roms/{pack['rom_filename']}"
                        core_path = f"client/cores/{pack['core_filename']}"
                        client.launcher.launch(core_path, rom_path, is_host=is_host, connect_ip=connect_ip)
                    else:
                        print("Pack not found.")
                else:
                    print("Usage: launch <pack_id> [--host | --connect <ip>]")
            else:
                if command != "":
                    print("Commands: status <text>, play <game>, create <room_id> <game>, join <room_id>, packs, sync <pack_id>, launch <pack_id>, quit")
        except KeyboardInterrupt:
            await client.disconnect()
            break
        except EOFError:
            await client.disconnect()
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
