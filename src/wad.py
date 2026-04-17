import struct

from models import DoomMap, Linedef, LumpEntry, Vertex


class WadArchive:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.lumps: list[LumpEntry] = []
        self.data: bytes = b""
        self.load()

    def load(self) -> None:
        with open(self.filename, "rb") as file_handle:
            self.data = file_handle.read()

        wad_type, num_lumps, dir_offset = struct.unpack("<4sii", self.data[:12])

        if wad_type not in (b"IWAD", b"PWAD"):
            raise ValueError("Not a valid WAD file")

        for index in range(num_lumps):
            offset = dir_offset + index * 16
            lump_offset, lump_size, lump_name = struct.unpack(
                "<ii8s", self.data[offset : offset + 16]
            )
            name = lump_name.rstrip(b"\0").decode("ascii", errors="ignore")
            self.lumps.append(LumpEntry(name=name, offset=lump_offset, size=lump_size))

    def find_lump_index(self, lump_name: str) -> int | None:
        for index, lump in enumerate(self.lumps):
            if lump.name == lump_name:
                return index
        return None

    def list_map_names(self) -> list[str]:
        map_names: list[str] = []
        for lump in self.lumps:
            name = lump.name
            if (len(name) == 4 and name.startswith("E")) or name.startswith("MAP"):
                map_names.append(name)
        return map_names


class DoomMapParser:
    MAP_CHILD_LUMP_NAMES = {"THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SECTORS"}

    def __init__(self, wad_archive: WadArchive) -> None:
        self.wad_archive = wad_archive

    def load_map(self, map_name: str) -> DoomMap:
        index = self.wad_archive.find_lump_index(map_name)
        if index is None:
            raise ValueError("Map not found")

        needed: dict[str, LumpEntry] = {}
        for lump_index in range(index + 1, min(index + 12, len(self.wad_archive.lumps))):
            lump = self.wad_archive.lumps[lump_index]
            if lump.name in self.MAP_CHILD_LUMP_NAMES:
                needed[lump.name] = lump

        doom_map = DoomMap()
        self._load_vertexes(needed, doom_map)
        self._load_linedefs(needed, doom_map)
        return doom_map

    def _load_vertexes(self, needed: dict[str, LumpEntry], doom_map: DoomMap) -> None:
        lump = needed.get("VERTEXES")
        if lump is None:
            return

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        for i in range(0, len(raw), 4):
            x, y = struct.unpack("<hh", raw[i : i + 4])
            doom_map.vertexes.append(Vertex(x, y))

    def _load_linedefs(self, needed: dict[str, LumpEntry], doom_map: DoomMap) -> None:
        lump = needed.get("LINEDEFS")
        if lump is None:
            return

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        for i in range(0, len(raw), 14):
            values = struct.unpack("<hhhhhhh", raw[i : i + 14])
            doom_map.linedefs.append(Linedef(*values))
