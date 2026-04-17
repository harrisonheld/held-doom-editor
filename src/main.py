import sys
import struct
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QAction, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QWidget,
)


# --------------------------------------------------
# Doom structures
# --------------------------------------------------

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


class DoomMap:
    def __init__(self):
        self.vertexes = []
        self.linedefs = []


# --------------------------------------------------
# WAD loader
# --------------------------------------------------

class WadFile:
    def __init__(self, filename):
        self.filename = filename
        self.lumps = []
        self.data = b""
        self.load()

    def load(self):
        with open(self.filename, "rb") as f:
            self.data = f.read()

        wad_type, num_lumps, dir_offset = struct.unpack(
            "<4sii", self.data[:12]
        )

        if wad_type not in (b"IWAD", b"PWAD"):
            raise ValueError("Not a valid WAD file")

        for i in range(num_lumps):
            off = dir_offset + i * 16
            lump_offset, lump_size, lump_name = struct.unpack(
                "<ii8s", self.data[off:off + 16]
            )

            lump_name = lump_name.rstrip(b"\0").decode("ascii", errors="ignore")
            self.lumps.append(
                {
                    "name": lump_name,
                    "offset": lump_offset,
                    "size": lump_size,
                }
            )

    def get_lump_data(self, name):
        for lump in self.lumps:
            if lump["name"] == name:
                a = lump["offset"]
                b = a + lump["size"]
                return self.data[a:b]
        return None

    def load_map(self, map_name):
        index = None

        for i, lump in enumerate(self.lumps):
            if lump["name"] == map_name:
                index = i
                break

        if index is None:
            raise ValueError("Map not found")

        needed = {}
        names = ["THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SECTORS"]

        for j in range(index + 1, min(index + 12, len(self.lumps))):
            name = self.lumps[j]["name"]
            if name in names:
                needed[name] = self.lumps[j]

        doom_map = DoomMap()

        # Vertexes
        if "VERTEXES" in needed:
            lump = needed["VERTEXES"]
            raw = self.data[lump["offset"]: lump["offset"] + lump["size"]]

            for i in range(0, len(raw), 4):
                x, y = struct.unpack("<hh", raw[i:i + 4])
                doom_map.vertexes.append(Vertex(x, y))

        # Linedefs
        if "LINEDEFS" in needed:
            lump = needed["LINEDEFS"]
            raw = self.data[lump["offset"]: lump["offset"] + lump["size"]]

            for i in range(0, len(raw), 14):
                vals = struct.unpack("<hhhhhhh", raw[i:i + 14])
                doom_map.linedefs.append(Linedef(*vals))

        return doom_map


# --------------------------------------------------
# Canvas
# --------------------------------------------------

class MapCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.map = None
        self.zoom = 0.5
        self.offset_x = 0
        self.offset_y = 0
        self.last_mouse = None
        self.setMinimumSize(800, 600)

    def set_map(self, doom_map):
        self.map = doom_map
        self.update()

    def world_to_screen(self, x, y):
        sx = self.width() / 2 + (x * self.zoom) + self.offset_x
        sy = self.height() / 2 - (y * self.zoom) + self.offset_y
        return sx, sy

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)

        if not self.map:
            return

        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(Qt.white, 1))

        for line in self.map.linedefs:
            if line.v1 >= len(self.map.vertexes):
                continue
            if line.v2 >= len(self.map.vertexes):
                continue

            a = self.map.vertexes[line.v1]
            b = self.map.vertexes[line.v2]

            x1, y1 = self.world_to_screen(a.x, a.y)
            x2, y2 = self.world_to_screen(b.x, b.y)

            p.drawLine(x1, y1, x2, y2)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()

        if delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1

        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.last_mouse = event.position()

    def mouseMoveEvent(self, event):
        if self.last_mouse is not None:
            pos = event.position()
            diff = pos - self.last_mouse
            self.offset_x += diff.x()
            self.offset_y += diff.y()
            self.last_mouse = pos
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.last_mouse = None


# --------------------------------------------------
# Main window
# --------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Python Doom WAD Editor")
        self.resize(1200, 800)

        self.canvas = MapCanvas()
        self.setCentralWidget(self.canvas)

        self.build_menu()

    def build_menu(self):
        menu = self.menuBar().addMenu("File")

        open_action = QAction("Open WAD", self)
        open_action.triggered.connect(self.open_wad)
        menu.addAction(open_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

    def open_wad(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open WAD",
            "",
            "WAD Files (*.wad)"
        )

        if not filename:
            return

        try:
            wad = WadFile(filename)

            map_names = []
            for lump in wad.lumps:
                name = lump["name"]
                if (
                    len(name) == 4 and name.startswith("E")
                    or name.startswith("MAP")
                ):
                    map_names.append(name)

            if not map_names:
                raise ValueError("No maps found")

            doom_map = wad.load_map(map_names[0])
            self.canvas.set_map(doom_map)

            self.statusBar().showMessage(
                f"Loaded {Path(filename).name} : {map_names[0]}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# --------------------------------------------------
# main
# --------------------------------------------------

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
