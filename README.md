# Retro Online - Master Spec Implementation

This project is a social multiplayer platform for the R36S console.
It consists of a central server (backend) that coordinates user states and rooms, and a local client that synchronizes official game packs and automatically launches RetroArch Netplay.

## Project Vision
To connect R36S consoles, simplify retro multiplayer, and create a persistent, automatic community experience akin to an online retro arcade.

### Features (MVP)
- **Real-time Status**: Broadcasts users' online presence using WebSockets.
- **Rooms**: Creation of and joining rooms for specific games.
- **Client Emulation**: A minimal CLI client mimicking the final R36S daemon functionality.

## Tech Stack
- **Server**: Python 3, FastAPI, Uvicorn, WebSockets.
- **Client**: Python 3, `websockets`, `asyncio`.

## Project Structure
```text
.
├── client
│   ├── configs
│   ├── launcher
│   ├── main.py
│   ├── netplay
│   ├── sync
│   ├── ui
│   └── websocket
├── requirements.txt
└── server
    ├── api
    ├── database
    ├── friends
    ├── main.py
    ├── multiplayer
    ├── packs
    ├── rooms
    ├── services
    ├── users
    └── websocket
```

## Running the Server
```bash
pip install -r requirements.txt
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

## Running the Client
```bash
python -m client.main [username]
```

### Client Commands
- `status <text>`: Set your status.
- `play <game>`: Set status to "En partida" and specify the game.
- `create <room_id> <game>`: Create a game room.
- `join <room_id>`: Join an existing game room.
- `quit`: Exit the client.
