from textual.app import ComposeResult
from textual.widgets import Label, OptionList, Footer, Header, DataTable
from textual.screen import Screen
from textual.containers import Vertical, Horizontal

class BaseRetroScreen(Screen):
    def compose(self) -> ComposeResult:
        title = getattr(self, "TITLE", "RETRO ONLINE")
        yield Label(title, classes="header_title")
        yield from self.get_content()
        yield Footer()

    def get_content(self):
        yield Vertical()

class MainMenuScreen(BaseRetroScreen):
    TITLE = "RETRO ONLINE"

    def get_content(self):
        yield OptionList(
            "Sala General",
            "Crear Sala",
            "Unirse a Sala",
            "Salas por Consola",
            "Amigos Online",
            "Sincronizar Packs",
            "Configuración",
            "Cerrar Sesión",
            id="main_menu"
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.prompt == "Cerrar Sesión":
            self.app.exit()
        elif event.option.prompt == "Sala General":
            self.app.push_screen("sala_general")
        elif event.option.prompt == "Sincronizar Packs":
            self.app.push_screen("sincronizar_packs")
        elif event.option.prompt == "Unirse a Sala":
            self.app.push_screen("keyboard")
        elif event.option.prompt == "Crear Sala":
            self.app.push_screen("create_room")
        else:
            # Catch-all for non-implemented menus (Amigos, Consolas, Configuración)
            self.app.push_screen("placeholder")

class SalaGeneralScreen(BaseRetroScreen):
    TITLE = "SALA GENERAL"

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("Status", "User", "Activity")
        self.update_users(self.app.client.users_online)

    def update_users(self, users):
        table = self.query_one(DataTable)
        table.clear()

        status_map = {
            "Online": "●",
            "En partida": "▲",
            "Offline": "○"
        }

        for u in users:
            symbol = status_map.get(u['status'], "■")
            activity = u.get("game") or u['status']
            if u.get("room_id"):
                activity += f" (Room: {u['room_id']})"
            table.add_row(symbol, u['username'], activity)

        count_label = self.query_one("#online_count", Label)
        count_label.update(f"USUARIOS ONLINE: {len(users)}")

    def get_content(self):
        yield Label("USUARIOS ONLINE: 0", id="online_count")
        yield DataTable(cursor_type="row")

    def on_key(self, event):
        if event.key == "escape" or event.key == "b":
            self.app.pop_screen()

class SincronizarPacksScreen(BaseRetroScreen):
    TITLE = "SINCRONIZAR PACKS"

    def on_mount(self):
        # We fetch packs asynchronously using the client sync manager
        self.run_worker(self.load_packs())

    async def load_packs(self):
        import asyncio
        self.packs = await asyncio.to_thread(self.app.client.sync_manager.fetch_packs)
        table = self.query_one(DataTable)
        # Store column keys
        self.col_id, self.col_game, self.col_sys, self.col_status = table.add_columns("ID", "Game", "System", "Status")
        for p in self.packs:
            table.add_row(str(p['id']), p['game'], p['system'], "[DESCARGAR]")

        count_label = self.query_one("#pack_count", Label)
        count_label.update(f"Packs disponibles: {len(self.packs)}")

    def get_content(self):
        yield Label("Packs disponibles: cargando...", id="pack_count")
        yield DataTable(cursor_type="row")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one(DataTable)
        row_key = event.row_key

        pack_id_str = table.get_cell(row_key, self.col_id)
        pack_id = int(pack_id_str)

        pack = next((p for p in self.packs if p['id'] == pack_id), None)
        if pack:
            # Show downloading status visually
            table.update_cell(row_key, self.col_status, "[...]")
            import asyncio
            await asyncio.to_thread(self.app.client.sync_manager.sync_pack, pack['id'], pack['rom_filename'], pack['core_filename'])
            table.update_cell(row_key, self.col_status, "[OK]")

    def on_key(self, event):
        if event.key == "escape" or event.key == "b":
            self.app.pop_screen()

class KeyboardScreen(BaseRetroScreen):
    TITLE = "TECLADO VIRTUAL"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_input = ""

    def compose(self) -> ComposeResult:
        yield Label(self.TITLE, classes="header_title")
        yield Label("Ingresa el código de la sala:", id="keyboard_prompt")
        yield Label(" ", id="keyboard_input")
        yield DataTable(cursor_type="cell", id="keyboard_grid")
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.show_header = False
        keys = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
            ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
            ["K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
            ["U", "V", "W", "X", "Y", "Z", "-", "_", "DEL", "OK"]
        ]
        for i in range(10):
            table.add_column(str(i))
        for row in keys:
            table.add_row(*row)

    async def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        val = event.value
        input_label = self.query_one("#keyboard_input")

        if val == "DEL":
            self.current_input = self.current_input[:-1]
        elif val == "OK":
            room_id = self.current_input.lower()
            self.app.pop_screen()
            # Join the room with the selected code
            if room_id and len(room_id) > 0:
                await self.app.client.join_room(room_id)
                # DO NOT push lobby screen optimistically. We will push it on 'room_joined' confirmation.
        else:
            self.current_input += val

        display_text = self.current_input if len(self.current_input) > 0 else " "
        input_label.update(display_text)

    def on_key(self, event):
        if event.key == "escape" or event.key == "b":
            self.app.pop_screen()

class RoomLobbyScreen(BaseRetroScreen):
    TITLE = "SALA DE ESPERA"

    def compose(self) -> ComposeResult:
        yield Label(self.TITLE, classes="header_title")
        yield Label("Esperando jugadores...", id="room_status")
        yield OptionList(
            "Marcar como READY",
            "Abandonar Sala",
            id="room_options"
        )
        yield Footer()

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.prompt == "Marcar como READY":
            await self.app.client.set_ready()
            self.query_one("#room_status").update("Estado: LISTO. Esperando a los demás...")
        elif event.option.prompt == "Abandonar Sala":
            # Just popping for now, real abandon logic requires a backend endpoint which MVP lacks
            self.app.pop_screen()

    def on_key(self, event):
        if event.key == "escape" or event.key == "b":
            self.app.pop_screen()

class CreateRoomScreen(BaseRetroScreen):
    TITLE = "CREAR SALA"

    def on_mount(self):
        self.run_worker(self.load_packs())

    async def load_packs(self):
        import asyncio
        self.packs = await asyncio.to_thread(self.app.client.sync_manager.fetch_packs)
        table = self.query_one(DataTable)
        self.col_id, self.col_game = table.add_columns("ID", "Game")
        for p in self.packs:
            table.add_row(str(p['id']), p['game'])

    def compose(self) -> ComposeResult:
        yield Label(self.TITLE, classes="header_title")
        yield Label("Selecciona un juego para crear la sala:")
        yield DataTable(cursor_type="row")
        yield Footer()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one(DataTable)
        row_key = event.row_key
        pack_id_str = table.get_cell(row_key, self.col_id)

        # For MVP we will auto-generate a room_id to keep it simple, or we could ask for one
        import random
        room_id = f"sala_{random.randint(100, 999)}"

        await self.app.client.create_room(room_id, pack_id_str)
        self.app.pop_screen()
        # The room_lobby will be pushed automatically by the app when confirmation arrives

    def on_key(self, event):
        if event.key == "escape" or event.key == "b":
            self.app.pop_screen()

class PlaceholderScreen(BaseRetroScreen):
    TITLE = "PRÓXIMAMENTE"

    def compose(self) -> ComposeResult:
        yield Label(self.TITLE, classes="header_title")
        yield Label("Esta sección estará disponible en futuras actualizaciones.", id="room_status")
        yield Footer()

    def on_key(self, event):
        if event.key == "escape" or event.key == "b" or event.key == "enter":
            self.app.pop_screen()
