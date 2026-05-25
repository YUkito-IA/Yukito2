import sys
from client.ui.app import RetroOnlineApp

if __name__ == "__main__":
    # If no username is passed, start empty to trigger the AuthScreen
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    app = RetroOnlineApp(username)
    app.run()
