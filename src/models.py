from dataclasses import dataclass, field


@dataclass
class Vertex:
    x: int
    y: int


@dataclass
class Linedef:
    v1: int
    v2: int
    flags: int
    special: int
    tag: int
    right: int
    left: int


@dataclass
class LumpEntry:
    name: str
    offset: int
    size: int


@dataclass
class Sector:
    vertex_indices: list[int]
    info: "SectorInfo" = field(default_factory=lambda: SectorInfo())


@dataclass
class SectorInfo:
    floor_height: int = 0
    ceiling_height: int = 128
    light_level: int = 160
    tag: int = 0


class DoomMap:
    def __init__(self) -> None:
        self.vertexes: list[Vertex] = []
        self.linedefs: list[Linedef] = []
        self.sectors: list[Sector] = []
