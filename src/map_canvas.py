import math
from typing import Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from models import DoomMap


class MapCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.map: Optional[DoomMap] = None
        self.zoom: float = 0.5
        self.offset_x: float = 0
        self.offset_y: float = 0
        self.grid_size: int = 64
        self.last_mouse: Optional[QPointF] = None
        self.hover_mouse: Optional[QPointF] = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(800, 600)

    def set_map(self, doom_map: DoomMap) -> None:
        self.map = doom_map
        self.update()

    def world_to_screen(self, x: int, y: int) -> tuple[float, float]:
        sx = self.width() / 2 + (x * self.zoom) + self.offset_x
        sy = self.height() / 2 - (y * self.zoom) + self.offset_y
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        wx = (sx - (self.width() / 2) - self.offset_x) / self.zoom
        wy = ((self.height() / 2) + self.offset_y - sy) / self.zoom
        return wx, wy

    def nearest_grid_point(self, sx: float, sy: float) -> tuple[int, int]:
        wx, wy = self.screen_to_world(sx, sy)
        gx = round(wx / self.grid_size) * self.grid_size
        gy = round(wy / self.grid_size) * self.grid_size
        return gx, gy

    def draw_grid(self, painter: QPainter) -> None:
        if self.zoom <= 0:
            return

        spacing_pixels = self.grid_size * self.zoom
        draw_grid_step = self.grid_size
        if spacing_pixels < 8:
            draw_grid_step *= math.ceil(8 / spacing_pixels)

        left_world, top_world = self.screen_to_world(0, 0)
        right_world, bottom_world = self.screen_to_world(self.width(), self.height())

        min_x = min(left_world, right_world)
        max_x = max(left_world, right_world)
        min_y = min(bottom_world, top_world)
        max_y = max(bottom_world, top_world)

        start_x = int(math.floor(min_x / draw_grid_step) * draw_grid_step)
        end_x = int(math.ceil(max_x / draw_grid_step) * draw_grid_step)
        start_y = int(math.floor(min_y / draw_grid_step) * draw_grid_step)
        end_y = int(math.ceil(max_y / draw_grid_step) * draw_grid_step)

        grid_pen = QPen(QColor(170, 170, 170), 1)
        painter.setPen(grid_pen)

        for world_x in range(start_x, end_x + draw_grid_step, draw_grid_step):
            screen_x, _ = self.world_to_screen(world_x, 0)
            painter.drawLine(QPointF(screen_x, 0), QPointF(screen_x, self.height()))

        for world_y in range(start_y, end_y + draw_grid_step, draw_grid_step):
            _, screen_y = self.world_to_screen(0, world_y)
            painter.drawLine(QPointF(0, screen_y), QPointF(self.width(), screen_y))

    def draw_grid_highlight(self, painter: QPainter) -> None:
        if self.hover_mouse is None:
            return

        grid_x, grid_y = self.nearest_grid_point(self.hover_mouse.x(), self.hover_mouse.y())
        sx, sy = self.world_to_screen(grid_x, grid_y)
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.setBrush(QColor(220, 220, 220, 100))
        painter.drawEllipse(QPointF(sx, sy), 4, 4)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        self.draw_grid(painter)
        self.draw_grid_highlight(painter)

        if not self.map:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))

        for line in self.map.linedefs:
            if line.v1 >= len(self.map.vertexes):
                continue
            if line.v2 >= len(self.map.vertexes):
                continue

            a = self.map.vertexes[line.v1]
            b = self.map.vertexes[line.v2]
            x1, y1 = self.world_to_screen(a.x, a.y)
            x2, y2 = self.world_to_screen(b.x, b.y)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        self.hover_mouse = event.position()
        if event.button() == Qt.MouseButton.MiddleButton:
            self.last_mouse = event.position()
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.hover_mouse = event.position()

        if self.last_mouse is None:
            self.update()
            return

        pos = event.position()
        diff = pos - self.last_mouse
        self.offset_x += diff.x()
        self.offset_y += diff.y()
        self.last_mouse = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.hover_mouse = event.position()
        if event.button() == Qt.MouseButton.MiddleButton:
            self.last_mouse = None
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_BracketLeft:
            self.grid_size = max(1, self.grid_size // 2)
            self.update()
            return

        if event.key() == Qt.Key.Key_BracketRight:
            self.grid_size *= 2
            self.update()
            return

        super().keyPressEvent(event)
