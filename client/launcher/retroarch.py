import subprocess
import os

class RetroArchLauncher:
    def __init__(self, retroarch_bin="retroarch"):
        self.retroarch_bin = retroarch_bin

    def launch(self, core_path, rom_path, is_host=False, connect_ip=None):
        if not os.path.exists(core_path):
            print(f"Error: Core not found at {core_path}")
            return False

        if not os.path.exists(rom_path):
            print(f"Error: ROM not found at {rom_path}")
            return False

        command = [
            self.retroarch_bin,
            "-L", core_path,
            rom_path
        ]

        if is_host:
            command.append("--host")
        elif connect_ip:
            command.extend(["--connect", connect_ip])

        print(f"Launching RetroArch with command: {' '.join(command)}")
        try:
            # Execute the actual process. We use Popen so it runs in background
            # and doesn't block the client CLI completely.
            subprocess.Popen(command)
            print("RetroArch launched successfully.")
            return True
        except Exception as e:
            print(f"Failed to launch RetroArch: {e}")
            return False
