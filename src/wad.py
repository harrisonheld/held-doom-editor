import logging
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from models import DoomMap, Linedef, LumpEntry, SectorDef, SectorRegion, Sidedef, Thing, Vertex


logger = logging.getLogger(__name__)


@dataclass
class WADLumpData:
    name: str
    data: bytes


class WadArchive:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.lumps: list[LumpEntry] = []
        self.data: bytes = b""
        self.load()

    def load(self) -> None:
        logger.info("Loading WAD: %s", str(Path(self.filename).resolve()))
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

        logger.info(
            "Loaded WAD %s with %d lumps",
            str(Path(self.filename).resolve()),
            len(self.lumps),
        )

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

    def get_palette(self) -> list[tuple[int, int, int]] | None:
        lump_index = self.find_lump_index("PLAYPAL")
        if lump_index is None:
            return None

        lump = self.lumps[lump_index]
        raw = self.data[lump.offset : lump.offset + lump.size]
        if len(raw) < 256 * 3:
            return None

        palette: list[tuple[int, int, int]] = []
        for i in range(256):
            base = i * 3
            palette.append((raw[base], raw[base + 1], raw[base + 2]))
        return palette

    def get_flat_data(self, flat_name: str) -> bytes | None:
        normalized = flat_name.strip().upper()[:8]
        if not normalized:
            return None

        # Flats are usually inside F_START/F_END or FF_START/FF_END blocks.
        in_flat_block = False
        for lump in self.lumps:
            lump_name = lump.name.upper()
            if lump_name in {"F_START", "FF_START"}:
                in_flat_block = True
                continue
            if lump_name in {"F_END", "FF_END"}:
                in_flat_block = False
                continue

            if in_flat_block and lump_name == normalized and lump.size >= 4096:
                return self.data[lump.offset : lump.offset + 4096]

        # Fallback: some WADs place flat-like lumps outside marker blocks.
        for lump in self.lumps:
            if lump.name.upper() == normalized and lump.size >= 4096:
                return self.data[lump.offset : lump.offset + 4096]

        return None

    def list_thing_ids(self, map_name: str | None = None) -> list[int]:
        thing_ids: set[int] = set()

        if map_name is not None:
            lump = self._get_map_child_lump(map_name, "THINGS")
            if lump is None:
                logger.debug("No THINGS lump found for map %s in %s", map_name, self.filename)
                return []
            thing_ids.update(self._extract_thing_ids_from_lump(lump))
            logger.debug(
                "Extracted %d Thing IDs from map %s in %s",
                len(thing_ids),
                map_name,
                self.filename,
            )
            return sorted(thing_ids)

        for candidate_map in self.list_map_names():
            lump = self._get_map_child_lump(candidate_map, "THINGS")
            if lump is None:
                continue
            thing_ids.update(self._extract_thing_ids_from_lump(lump))

        logger.debug("Extracted %d unique Thing IDs from WAD %s", len(thing_ids), self.filename)

        return sorted(thing_ids)

    def _get_map_child_lump(self, map_name: str, child_name: str) -> LumpEntry | None:
        map_index = self.find_lump_index(map_name)
        if map_index is None:
            return None

        for lump_index in range(map_index + 1, min(map_index + 12, len(self.lumps))):
            lump = self.lumps[lump_index]
            if lump.name == child_name:
                return lump
        return None

    def _extract_thing_ids_from_lump(self, lump: LumpEntry) -> set[int]:
        result: set[int] = set()
        raw = self.data[lump.offset : lump.offset + lump.size]
        for i in range(0, len(raw), 10):
            if i + 10 > len(raw):
                break
            _, _, _, thing_type, _ = struct.unpack("<hhhhh", raw[i : i + 10])
            result.add(int(thing_type))
        return result

    def get_map_doom_map(self, map_name: str) -> DoomMap:
        parser = DoomMapParser(self)
        return parser.load_map(map_name)

    def save_map(self, map_name: str, doom_map: DoomMap, filename: str | None = None) -> str:
        writer = WadWriter(self)
        return writer.save_map(map_name, doom_map, filename)


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
        self._load_things(needed, doom_map)
        self._load_vertexes(needed, doom_map)
        self._load_linedefs(needed, doom_map)
        self._load_sidedefs(needed, doom_map)
        self._load_sector_defs(needed, doom_map)
        self._build_sector_regions(doom_map)
        return doom_map

    def _load_things(self, needed: dict[str, LumpEntry], doom_map: DoomMap) -> None:
        lump = needed.get("THINGS")
        if lump is None:
            return

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        for i in range(0, len(raw), 10):
            x, y, angle, thing_type, flags = struct.unpack("<hhhhh", raw[i : i + 10])
            doom_map.things.append(
                Thing(
                    x=x,
                    y=y,
                    angle=angle,
                    thing_type=thing_type,
                    flags=flags,
                )
            )

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

    def _load_sidedefs(self, needed: dict[str, LumpEntry], doom_map: DoomMap) -> None:
        lump = needed.get("SIDEDEFS")
        if lump is None:
            return

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        for i in range(0, len(raw), 30):
            x_offset, y_offset, upper, lower, middle, sector_index = struct.unpack(
                "<hh8s8s8sh", raw[i : i + 30]
            )
            doom_map.sidedefs.append(
                Sidedef(
                    x_offset=x_offset,
                    y_offset=y_offset,
                    upper_texture=upper.rstrip(b"\0").decode("ascii", errors="ignore"),
                    lower_texture=lower.rstrip(b"\0").decode("ascii", errors="ignore"),
                    middle_texture=middle.rstrip(b"\0").decode("ascii", errors="ignore"),
                    sector_index=sector_index,
                )
            )

    def _load_sector_defs(self, needed: dict[str, LumpEntry], doom_map: DoomMap) -> None:
        lump = needed.get("SECTORS")
        if lump is None:
            return

        raw = self.wad_archive.data[lump.offset : lump.offset + lump.size]
        for i in range(0, len(raw), 26):
            floor, ceiling, floor_tex, ceil_tex, light, special, tag = struct.unpack(
                "<hh8s8shhh", raw[i : i + 26]
            )
            doom_map.sector_defs.append(
                SectorDef(
                    floor_height=floor,
                    ceiling_height=ceiling,
                    floor_texture=floor_tex.rstrip(b"\0").decode("ascii", errors="ignore"),
                    ceiling_texture=ceil_tex.rstrip(b"\0").decode("ascii", errors="ignore"),
                    light_level=light,
                    special_type=special,
                    tag=tag,
                )
            )

    def _build_sector_regions(self, doom_map: DoomMap) -> None:
        edges_by_sector: dict[int, list[tuple[int, int]]] = defaultdict(list)

        for linedef in doom_map.linedefs:
            if 0 <= linedef.front_sidedef < len(doom_map.sidedefs):
                sector_index = doom_map.sidedefs[linedef.front_sidedef].sector_index
                if sector_index >= 0:
                    edges_by_sector[sector_index].append((linedef.v1, linedef.v2))

            if 0 <= linedef.back_sidedef < len(doom_map.sidedefs):
                sector_index = doom_map.sidedefs[linedef.back_sidedef].sector_index
                if sector_index >= 0:
                    edges_by_sector[sector_index].append((linedef.v2, linedef.v1))

        for sector_index in range(len(doom_map.sector_defs)):
            loops = self._build_loops(edges_by_sector.get(sector_index, []))
            if not loops:
                continue

            best_loop = max(loops, key=lambda loop: abs(self._loop_area(doom_map, loop)))
            doom_map.sector_regions.append(
                SectorRegion(sector_index=sector_index, vertex_indices=best_loop)
            )

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


class WadWriter:
    MAP_LUMP_ORDER = ["THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SECTORS"]

    def __init__(self, wad_archive: WadArchive) -> None:
        self.wad_archive = wad_archive

    def save_map(self, map_name: str, doom_map: DoomMap, filename: str | None = None) -> str:
        output_filename = filename or self.wad_archive.filename
        map_lumps = self._build_map_lumps(doom_map)
        written_lumps = self._rewrite_lumps(map_name, map_lumps)
        self._write_wad_file(output_filename, written_lumps)
        return output_filename

    def _build_map_lumps(self, doom_map: DoomMap) -> dict[str, bytes]:
        return {
            "THINGS": self._serialize_things(doom_map),
            "LINEDEFS": self._serialize_linedefs(doom_map),
            "SIDEDEFS": self._serialize_sidedefs(doom_map),
            "VERTEXES": self._serialize_vertexes(doom_map),
            "SECTORS": self._serialize_sector_defs(doom_map),
        }

    def _serialize_things(self, doom_map: DoomMap) -> bytes:
        if hasattr(doom_map, "things"):
            data = bytearray()
            for thing in doom_map.things:
                data.extend(struct.pack("<hhhhh", thing.x, thing.y, thing.angle, thing.thing_type, thing.flags))
            return bytes(data)

        return self._get_original_lump_data("THINGS")

    def _serialize_vertexes(self, doom_map: DoomMap) -> bytes:
        data = bytearray()
        for vertex in doom_map.vertexes:
            data.extend(struct.pack("<hh", vertex.x, vertex.y))
        return bytes(data)

    def _serialize_linedefs(self, doom_map: DoomMap) -> bytes:
        data = bytearray()
        for linedef in doom_map.linedefs:
            data.extend(
                struct.pack(
                    "<hhhhhhh",
                    linedef.v1,
                    linedef.v2,
                    linedef.flags,
                    linedef.special,
                    linedef.tag,
                    linedef.front_sidedef,
                    linedef.back_sidedef,
                )
            )
        return bytes(data)

    def _serialize_sidedefs(self, doom_map: DoomMap) -> bytes:
        data = bytearray()
        for sidedef in doom_map.sidedefs:
            data.extend(
                struct.pack(
                    "<hh8s8s8sh",
                    sidedef.x_offset,
                    sidedef.y_offset,
                    self._pack_name(sidedef.upper_texture),
                    self._pack_name(sidedef.lower_texture),
                    self._pack_name(sidedef.middle_texture),
                    sidedef.sector_index,
                )
            )
        return bytes(data)

    def _serialize_sector_defs(self, doom_map: DoomMap) -> bytes:
        data = bytearray()
        for sector_def in doom_map.sector_defs:
            data.extend(
                struct.pack(
                    "<hh8s8shhh",
                    sector_def.floor_height,
                    sector_def.ceiling_height,
                    self._pack_name(sector_def.floor_texture),
                    self._pack_name(sector_def.ceiling_texture),
                    sector_def.light_level,
                    sector_def.special_type,
                    sector_def.tag,
                )
            )
        return bytes(data)

    def _pack_name(self, value: str) -> bytes:
        return value.encode("ascii", errors="ignore")[:8].ljust(8, b"\0")

    def _get_original_lump_data(self, lump_name: str) -> bytes:
        for lump in self.wad_archive.lumps:
            if lump.name == lump_name:
                return self.wad_archive.data[lump.offset : lump.offset + lump.size]
        return b""

    def _rewrite_lumps(self, map_name: str, map_lumps: dict[str, bytes]) -> list[tuple[str, bytes]]:
        lumps: list[tuple[str, bytes]] = []
        index = self.wad_archive.find_lump_index(map_name)
        if index is None:
            raise ValueError("Map not found")

        # Copy everything before the map marker.
        for lump in self.wad_archive.lumps[: index + 1]:
            lumps.append((lump.name, self.wad_archive.data[lump.offset : lump.offset + lump.size]))

        # Replace the editable map lumps in canonical order.
        for lump_name in self.MAP_LUMP_ORDER:
            lumps.append((lump_name, map_lumps[lump_name]))

        # Preserve everything after the original map lumps by skipping the old block.
        skip_names = set(self.MAP_LUMP_ORDER)
        after_index = index + 1
        while after_index < len(self.wad_archive.lumps) and self.wad_archive.lumps[after_index].name in skip_names:
            after_index += 1

        for lump in self.wad_archive.lumps[after_index:]:
            lumps.append((lump.name, self.wad_archive.data[lump.offset : lump.offset + lump.size]))

        return lumps

    def _write_wad_file(self, filename: str, lumps: list[tuple[str, bytes]]) -> None:
        lump_entries: list[tuple[int, int, str]] = []
        data = bytearray(b"\0" * 12)

        for name, lump_data in lumps:
            offset = len(data)
            data.extend(lump_data)
            lump_entries.append((offset, len(lump_data), name))

        dir_offset = len(data)
        for offset, size, name in lump_entries:
            data.extend(struct.pack("<ii8s", offset, size, self._pack_name(name)))

        wad_type = self.wad_archive.data[:4]
        if wad_type not in (b"IWAD", b"PWAD"):
            wad_type = b"PWAD"

        header = struct.pack("<4sii", wad_type, len(lump_entries), dir_offset)
        data[0:12] = header

        with open(filename, "wb") as file_handle:
            file_handle.write(data)
