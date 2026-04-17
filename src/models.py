from dataclasses import dataclass


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


class DoomMap:
    def __init__(self) -> None:
        self.vertexes: list[Vertex] = []
        self.linedefs: list[Linedef] = []
