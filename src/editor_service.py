import logging
import re
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor, QImage

from models import DoomMap
from wad import DoomMapParser, WadArchive


logger = logging.getLogger(__name__)


class DoomEditorService:
    def __init__(self) -> None:
        self.current_wad: Optional[WadArchive] = None
        self.current_wad_filename: Optional[str] = None
        self.current_map_name: Optional[str] = None
        self.current_map: Optional[DoomMap] = None
        self.iwads: dict[str, WadArchive] = {}

    def load_wad(self, filename: str) -> list[str]:
        wad_path = str(Path(filename).resolve())
        logger.info("Opening WAD: %s", wad_path)
        self.current_wad = WadArchive(filename)
        self.current_wad_filename = filename
        self.current_map_name = None
        self._discover_iwads(Path(filename).parent)
        map_names = self.current_wad.list_map_names()
        if not map_names:
            raise ValueError("No maps found")
        logger.info("Found %d maps in %s", len(map_names), wad_path)
        return map_names

    def _discover_iwads(self, preferred_dir: Path) -> None:
        logger.info("Discovering IWADs in %s", str(preferred_dir.resolve()))
        discovered: dict[str, WadArchive] = {}
        search_dirs: list[Path] = [preferred_dir, Path.cwd()]

        for game, filename in (("doom1", "DOOM.WAD"), ("doom2", "DOOM2.WAD")):
            for directory in search_dirs:
                candidate = directory / filename
                if not candidate.exists():
                    continue
                try:
                    discovered[game] = WadArchive(str(candidate))
                    logger.info("Discovered %s IWAD at %s", game, str(candidate.resolve()))
                    break
                except Exception:
                    logger.warning("Failed to load IWAD candidate: %s", str(candidate.resolve()))
                    continue

        if self.current_wad is not None and self.current_wad_filename is not None:
            current_name = Path(self.current_wad_filename).name.upper()
            if current_name == "DOOM.WAD":
                discovered["doom1"] = self.current_wad
            if current_name == "DOOM2.WAD":
                discovered["doom2"] = self.current_wad

        self.iwads = discovered
        logger.info("IWAD profiles available: %s", ", ".join(sorted(self.iwads.keys())) or "none")

    def has_wad_loaded(self) -> bool:
        return self.current_wad is not None

    def list_current_maps(self) -> list[str]:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")
        return self.current_wad.list_map_names()

    def list_current_map_thing_ids(self) -> list[int]:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")
        if self.current_map_name is None:
            return []
        return self.current_wad.list_thing_ids(self.current_map_name)

    def list_wad_thing_ids(self) -> list[int]:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")
        return self.current_wad.list_thing_ids()

    def current_game_profile(self) -> str | None:
        if self.current_map_name is None:
            return None

        if re.fullmatch(r"MAP\d\d", self.current_map_name):
            return "doom2"
        if re.fullmatch(r"E\dM\d", self.current_map_name):
            return "doom1"
        return None

    def list_iwad_thing_ids_for_current_game(self) -> list[int]:
        game = self.current_game_profile()
        if game is None:
            logger.debug("No current game profile while listing IWAD Thing IDs")
            return []

        iwad = self.iwads.get(game)
        if iwad is None:
            logger.info("No IWAD loaded for game profile %s", game)
            return []
        return iwad.list_thing_ids()

    def get_flat_image_for_current_game(self, flat_name: str) -> QImage | None:
        if not flat_name or flat_name == "-":
            return None

        sources: list[WadArchive] = []
        if self.current_wad is not None:
            sources.append(self.current_wad)

        game = self.current_game_profile()
        if game is not None and game in self.iwads:
            sources.append(self.iwads[game])

        for key in sorted(self.iwads.keys()):
            archive = self.iwads[key]
            if archive not in sources:
                sources.append(archive)

        flat_data: bytes | None = None
        for source in sources:
            flat_data = source.get_flat_data(flat_name)
            if flat_data is not None:
                break

        if flat_data is None:
            return None

        palette: list[tuple[int, int, int]] | None = None
        for source in sources:
            palette = source.get_palette()
            if palette is not None:
                break

        return self._flat_to_image(flat_data, palette)

    def _flat_to_image(
        self,
        flat_data: bytes,
        palette: list[tuple[int, int, int]] | None,
    ) -> QImage:
        image = QImage(64, 64, QImage.Format.Format_RGB32)
        for y in range(64):
            for x in range(64):
                palette_index = flat_data[y * 64 + x]
                if palette is None:
                    color = QColor(palette_index, palette_index, palette_index)
                else:
                    r, g, b = palette[palette_index]
                    color = QColor(r, g, b)
                image.setPixelColor(x, y, color)
        return image

    def load_map(self, map_name: str) -> DoomMap:
        if self.current_wad is None:
            raise ValueError("No WAD is loaded")

        logger.info("Loading map: %s", map_name)
        self.current_map_name = map_name
        parser = DoomMapParser(self.current_wad)
        self.current_map = parser.load_map(map_name)
        logger.info(
            "Loaded map %s (things=%d, linedefs=%d, vertexes=%d)",
            map_name,
            len(self.current_map.things),
            len(self.current_map.linedefs),
            len(self.current_map.vertexes),
        )
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
        logger.info(
            "Saved map %s to %s",
            self.current_map_name,
            str(Path(output_filename).resolve()),
        )
        return output_filename
