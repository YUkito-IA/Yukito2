from textual.app import App
import asyncio

from client.main import RetroClient
from client.ui.screens import MainMenuScreen, SalaGeneralScreen, SincronizarPacksScreen, KeyboardScreen, RoomLobbyScreen, CreateRoomScreen, PlaceholderScreen

class RetroOnlineApp(App):
    CSS = """
    Screen {
        background: black;
        color: white;
    }
    .header_title {
        content-align: center middle;
        width: 100%;
        border: solid white;
        margin: 1 2;
        padding: 1;
        text-style: bold;
    }
    OptionList, DataTable {
        border: solid white;
        margin: 0 2;
        background: black;
        color: white;
    }
    OptionList > .option-list--option, DataTable {
        padding: 0 2;
    }
    OptionList > .option-list--option-highlighted {
        background: green;
        color: black;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: green;
        color: black;
        text-style: bold;
    }
    #keyboard_input {
        content-align: center middle;
        width: 100%;
        background: black;
        color: green;
        text-style: bold;
        margin: 1 0;
        padding: 1;
        border: solid white;
    }
    #keyboard_prompt {
        content-align: center middle;
        width: 100%;
    }
    """

    SCREENS = {
        "main_menu": MainMenuScreen,
        "sala_general": SalaGeneralScreen,
        "sincronizar_packs": SincronizarPacksScreen,
        "keyboard": KeyboardScreen,
        "room_lobby": RoomLobbyScreen,
        "create_room": CreateRoomScreen,
        "placeholder": PlaceholderScreen
    }

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.client = RetroClient(username)
        # Setup callbacks for UI updates
        self.client.on_state_update = self.on_state_update
        self.client.on_message = self.on_message

    def on_mount(self) -> None:
        # Start connection in background
        asyncio.create_task(self.client.connect())
        self.push_screen(MainMenuScreen())

    def on_state_update(self, users):
        # Notify the active screen if it cares about user updates
        if hasattr(self.screen, "update_users"):
            self.call_from_thread(self.screen.update_users, users)

    def on_message(self, message):
        self.log(message)
        # If we successfully join a room, push the lobby screen from the main app thread
        if "Joined room successfully" in message or "Room created successfully" in message:
            self.call_from_thread(self.push_screen, "room_lobby")
        # Ensure we display errors if connection or joining fails
        elif "[ERROR]" in message:
            self.call_from_thread(self.notify, message, severity="error")
        elif "[SYSTEM]" in message:
            self.call_from_thread(self.notify, message, severity="information")
