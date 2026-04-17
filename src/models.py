from dataclasses import dataclass


# https://doomwiki.org/wiki/Vertex
@dataclass
class Vertex:
    x: int
    y: int


# https://doomwiki.org/wiki/Linedef
@dataclass
class Linedef:
    v1: int
    v2: int
    flags: int
    special: int
    tag: int
    front_sidedef: int
    back_sidedef: int

# https://doomwiki.org/wiki/Sidedef
@dataclass
class Sidedef:
    x_offset: int
    y_offset: int
    upper_texture: str
    lower_texture: str
    middle_texture: str
    sector_index: int  # which sector this side faces.

# https://doomwiki.org/wiki/Sector
@dataclass
class SectorDef:
    floor_height: int = 0
    ceiling_height: int = 128
    floor_texture: str = "FLOOR0_1"
    ceiling_texture: str = "CEIL1_1"
    light_level: int = 160
    special_type: int = 0
    tag: int = 0

@dataclass
class LumpEntry:
    name: str
    offset: int
    size: int

@dataclass
class SectorRegion:
    sector_index: int
    vertex_indices: list[int]


class DoomMap:
    def __init__(self) -> None:
        self.vertexes: list[Vertex] = []
        self.linedefs: list[Linedef] = []
        self.sidedefs: list[Sidedef] = []
        self.sector_defs: list[SectorDef] = []
        self.sector_regions: list[SectorRegion] = []
