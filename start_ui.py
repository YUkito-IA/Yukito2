import sys
from client.ui.app import RetroOnlineApp

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "RetroUser"
    app = RetroOnlineApp(username)
    app.run()
