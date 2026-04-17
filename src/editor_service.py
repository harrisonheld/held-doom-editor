from typing import Optional

from models import DoomMap
from wad import DoomMapParser, WadArchive


class DoomEditorService:
    def __init__(self) -> None:
        self.current_wad: Optional[WadArchive] = None
        self.current_wad_filename: Optional[str] = None
        self.current_map_name: Optional[str] = None
        self.current_map: Optional[DoomMap] = None

    def load_wad(self, filename: str) -> list[str]:
        self.current_wad = WadArchive(filename)
        self.current_wad_filename = filename
        self.current_map_name = None
        map_names = self.current_wad.list_map_names()
        if not map_names:
            raise ValueError("No maps found")
        return map_names

    def has_wad_loaded(self) -> bool:
        return self.current_wad is not None

    def list_current_maps(self) -> list[str]:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")
        return self.current_wad.list_map_names()

    def load_map(self, map_name: str) -> DoomMap:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")

        self.current_map_name = map_name
        parser = DoomMapParser(self.current_wad)
        self.current_map = parser.load_map(map_name)
        return self.current_map

    def save_current_map(self, filename: str | None = None) -> str:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")
        if self.current_map_name is None:
            raise ValueError("No map is loaded")
        if self.current_map is None:
            raise ValueError("No editable map is loaded")

        output_filename = self.current_wad.save_map(self.current_map_name, self.current_map, filename)
        if filename is not None:
            self.current_wad_filename = output_filename
        return output_filename
