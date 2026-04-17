from typing import Optional

from models import DoomMap
from wad import DoomMapParser, WadArchive


class DoomEditorService:
    def __init__(self) -> None:
        self.current_wad: Optional[WadArchive] = None
        self.current_map_name: Optional[str] = None

    def load_wad(self, filename: str) -> list[str]:
        self.current_wad = WadArchive(filename)
        map_names = self.current_wad.list_map_names()
        if not map_names:
            raise ValueError("No maps found")
        return map_names

    def load_map(self, map_name: str) -> DoomMap:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")

        self.current_map_name = map_name
        parser = DoomMapParser(self.current_wad)
        return parser.load_map(map_name)
