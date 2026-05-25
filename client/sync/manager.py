import urllib.request
import json
import os

class SyncManager:
    def __init__(self, backend_url="http://localhost:8000"):
        self.backend_url = backend_url
        self.rom_dir = "client/roms"
        self.core_dir = "client/cores"
        os.makedirs(self.rom_dir, exist_ok=True)
        os.makedirs(self.core_dir, exist_ok=True)

    def fetch_packs(self):
        try:
            url = f"{self.backend_url}/packs"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Failed to fetch packs: {e}")
            return []

    def sync_pack(self, pack_id, rom_filename, core_filename):
        print(f"Syncing pack ID {pack_id}...")

        # Download ROM
        rom_url = f"{self.backend_url}/packs/download/{pack_id}/rom"
        rom_path = os.path.join(self.rom_dir, rom_filename)
        self._download_file(rom_url, rom_path)

        # Download Core
        core_url = f"{self.backend_url}/packs/download/{pack_id}/core"
        core_path = os.path.join(self.core_dir, core_filename)
        self._download_file(core_url, core_path)

        print(f"Pack {pack_id} synchronized.")
        return rom_path, core_path

    def _download_file(self, url, dest_path):
        if not os.path.exists(dest_path):
            print(f"Downloading {url} to {dest_path}...")
            try:
                urllib.request.urlretrieve(url, dest_path)
                print("Download complete.")
            except Exception as e:
                print(f"Download failed: {e}")
        else:
            print(f"File {dest_path} already exists. Skipping download.")
