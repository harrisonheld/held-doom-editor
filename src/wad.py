import struct
from collections import defaultdict

from models import DoomMap, Linedef, LumpEntry, Sector, SectorInfo, Vertex


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
        sidedef_sector_indices = self._load_sidedef_sector_indices(needed)
        sector_infos = self._load_sector_infos(needed)
        self._build_sectors(doom_map, sidedef_sector_indices, sector_infos)
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

    def _load_sidedef_sector_indices(self, needed: dict[str, LumpEntry]) -> list[int]:
        lump = needed.get("SIDEDEFS")
        if lump is None:
            return []

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        indices: list[int] = []
        for i in range(0, len(raw), 30):
            _, _, _, _, _, sector_index = struct.unpack("<hh8s8s8sh", raw[i : i + 30])
            indices.append(sector_index)
        return indices

    def _load_sector_infos(self, needed: dict[str, LumpEntry]) -> list[SectorInfo]:
        lump = needed.get("SECTORS")
        if lump is None:
            return []

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        sectors: list[SectorInfo] = []
        for i in range(0, len(raw), 26):
            floor, ceiling, _, _, light, _, tag = struct.unpack("<hh8s8shhh", raw[i : i + 26])
            sectors.append(
                SectorInfo(
                    floor_height=floor,
                    ceiling_height=ceiling,
                    light_level=light,
                    tag=tag,
                )
            )
        return sectors

    def _build_sectors(
        self,
        doom_map: DoomMap,
        sidedef_sector_indices: list[int],
        sector_infos: list[SectorInfo],
    ) -> None:
        edges_by_sector: dict[int, list[tuple[int, int]]] = defaultdict(list)

        for linedef in doom_map.linedefs:
            if 0 <= linedef.right < len(sidedef_sector_indices):
                sector_index = sidedef_sector_indices[linedef.right]
                if sector_index >= 0:
                    edges_by_sector[sector_index].append((linedef.v1, linedef.v2))

            if 0 <= linedef.left < len(sidedef_sector_indices):
                sector_index = sidedef_sector_indices[linedef.left]
                if sector_index >= 0:
                    edges_by_sector[sector_index].append((linedef.v2, linedef.v1))

        for sector_index, info in enumerate(sector_infos):
            loops = self._build_loops(edges_by_sector.get(sector_index, []))
            if not loops:
                doom_map.sectors.append(Sector(vertex_indices=[], info=info))
                continue

            best_loop = max(loops, key=lambda loop: abs(self._loop_area(doom_map, loop)))
            doom_map.sectors.append(Sector(vertex_indices=best_loop, info=info))

    def _build_loops(self, edges: list[tuple[int, int]]) -> list[list[int]]:
        remaining_edges = edges[:]
        loops: list[list[int]] = []

        while remaining_edges:
            start, next_vertex = remaining_edges.pop(0)
            loop = [start, next_vertex]
            current = next_vertex

            while current != start:
                next_edge_index = -1
                next_edge: tuple[int, int] | None = None

                for idx, (a, b) in enumerate(remaining_edges):
                    if a == current:
                        next_edge_index = idx
                        next_edge = (a, b)
                        break
                    if b == current:
                        next_edge_index = idx
                        next_edge = (b, a)
                        break

                if next_edge is None or next_edge_index < 0:
                    break

                remaining_edges.pop(next_edge_index)
                _, next_vertex = next_edge
                loop.append(next_vertex)
                current = next_vertex

            if len(loop) >= 4 and loop[-1] == start:
                loops.append(loop[:-1])

        return loops

    def _loop_area(self, doom_map: DoomMap, vertex_indices: list[int]) -> float:
        area = 0.0
        for i in range(len(vertex_indices)):
            a_index = vertex_indices[i]
            b_index = vertex_indices[(i + 1) % len(vertex_indices)]
            if a_index >= len(doom_map.vertexes) or b_index >= len(doom_map.vertexes):
                continue

            a = doom_map.vertexes[a_index]
            b = doom_map.vertexes[b_index]
            area += (a.x * b.y) - (b.x * a.y)
        return 0.5 * area
