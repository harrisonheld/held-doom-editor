import logging
import re
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor, QImage

from models import DoomMap
from wad import DoomMapParser, WadArchive, WadWriter


logger = logging.getLogger(__name__)


class DoomEditorService:
    def __init__(self) -> None:
        self.current_wad: Optional[WadArchive] = None
        self.current_wad_filename: Optional[str] = None
        self.current_map_name: Optional[str] = None
        self.current_map: Optional[DoomMap] = None
        self.iwads: dict[str, WadArchive] = {}
        self.active_game_profile: Optional[str] = None
        self.included_iwad_keys: list[str] = []

    def load_wad(self, filename: str) -> list[str]:
        wad_path = str(Path(filename).resolve())
        logger.info("Opening WAD: %s", wad_path)
        self.current_wad = WadArchive(filename)
        self.current_wad_filename = filename
        self.current_map_name = None
        self.active_game_profile = None
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
        if not self.included_iwad_keys:
            self.included_iwad_keys = list(sorted(self.iwads.keys()))
        else:
            self.included_iwad_keys = [
                key for key in self.included_iwad_keys if key in self.iwads
            ]
        logger.info("IWAD profiles available: %s", ", ".join(sorted(self.iwads.keys())) or "none")

    def refresh_iwads(self, preferred_dir: str | None = None) -> None:
        directory = Path.cwd() if preferred_dir is None else Path(preferred_dir)
        self._discover_iwads(directory)

    def available_iwads(self) -> dict[str, str]:
        return {key: archive.filename for key, archive in self.iwads.items()}

    def create_new_map(
        self,
        map_name: str,
        game_profile: str,
        included_iwad_keys: list[str],
    ) -> DoomMap:
        self.current_map_name = map_name
        self.current_map = DoomMap()
        self.active_game_profile = game_profile
        self.included_iwad_keys = [key for key in included_iwad_keys if key in self.iwads]
        logger.info(
            "Created new map %s with game profile %s and IWADs %s",
            map_name,
            game_profile,
            ", ".join(self.included_iwad_keys) or "none",
        )
        return self.current_map

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
        if self.active_game_profile is not None:
            return self.active_game_profile
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

        for key in self.included_iwad_keys:
            archive = self.iwads[key]
            if archive not in sources:
                sources.append(archive)

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

    def list_flat_names_for_current_game(self) -> list[str]:
        names: set[str] = set()
        sources: list[WadArchive] = []

        if self.current_wad is not None:
            sources.append(self.current_wad)

        for key in self.included_iwad_keys:
            archive = self.iwads[key]
            if archive not in sources:
                sources.append(archive)

        for key in sorted(self.iwads.keys()):
            archive = self.iwads[key]
            if archive not in sources:
                sources.append(archive)

        for source in sources:
            names.update(source.list_flat_names())

        return sorted(names)

    def list_flat_entries_for_current_game(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []

        if self.current_wad is not None and self.current_wad_filename is not None:
            wad_label = f"PWAD:{Path(self.current_wad_filename).name}"
            for flat_name in self.current_wad.list_flat_names():
                entries.append((flat_name, wad_label))

        for key in self.included_iwad_keys:
            archive = self.iwads.get(key)
            if archive is None:
                continue
            iwad_label = f"IWAD:{Path(archive.filename).name}"
            for flat_name in archive.list_flat_names():
                entries.append((flat_name, iwad_label))

        if not entries:
            for flat_name in self.list_flat_names_for_current_game():
                entries.append((flat_name, "unknown"))

        return sorted(entries, key=lambda item: (item[0], item[1]))

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
        self.active_game_profile = None
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
        if self.current_map_name is None:
            raise ValueError("No map is loaded")
        if self.current_map is None:
            raise ValueError("No editable map is loaded")

        if self.current_wad is None:
            if filename is None:
                raise ValueError("No WAD is loaded. Use Save As to create a new PWAD")
            output_filename = WadWriter.create_new_pwad(self.current_map_name, self.current_map, filename)
            self.current_wad = WadArchive(output_filename)
            self.current_wad_filename = output_filename
            logger.info(
                "Saved new PWAD for map %s to %s",
                self.current_map_name,
                str(Path(output_filename).resolve()),
            )
            return output_filename

        output_filename = self.current_wad.save_map(self.current_map_name, self.current_map, filename)
        if filename is not None:
            self.current_wad_filename = output_filename
        logger.info(
            "Saved map %s to %s",
            self.current_map_name,
            str(Path(output_filename).resolve()),
        )
        return output_filename
