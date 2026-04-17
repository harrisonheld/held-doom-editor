import math
from typing import Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from controls_manager import ControlsManager
from models import DoomMap, Linedef, Sector, Vertex


class MapCanvas(QWidget):
    sector_selected = Signal(int)

    def __init__(self, controls_manager: ControlsManager) -> None:
        super().__init__()
        self.controls_manager = controls_manager
        self.map: Optional[DoomMap] = None
        self.zoom: float = 0.5
        self.offset_x: float = 0
        self.offset_y: float = 0
        self.grid_size: int = 64
        self.last_mouse: Optional[QPointF] = None
        self.pan_start_mouse: Optional[QPointF] = None
        self.is_panning: bool = False
        self.hover_mouse: Optional[QPointF] = None
        self.pending_polygon: list[tuple[int, int]] = []
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(800, 600)

    def set_map(self, doom_map: DoomMap) -> None:
        self.map = doom_map
        self.pending_polygon.clear()
        self.update()

    def ensure_map(self) -> DoomMap:
        if self.map is None:
            self.map = DoomMap()
        return self.map

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

    def draw_pending_polygon(self, painter: QPainter) -> None:
        if not self.pending_polygon:
            return

        painter.setPen(QPen(QColor(255, 210, 120), 2))
        for i in range(1, len(self.pending_polygon)):
            x1, y1 = self.pending_polygon[i - 1]
            x2, y2 = self.pending_polygon[i]
            sx1, sy1 = self.world_to_screen(x1, y1)
            sx2, sy2 = self.world_to_screen(x2, y2)
            painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

        if self.hover_mouse is not None:
            hx, hy = self.nearest_grid_point(self.hover_mouse.x(), self.hover_mouse.y())
            px, py = self.pending_polygon[-1]
            sx1, sy1 = self.world_to_screen(px, py)
            sx2, sy2 = self.world_to_screen(hx, hy)
            painter.setPen(QPen(QColor(255, 210, 120, 150), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

        painter.setPen(QPen(QColor(255, 235, 180), 1))
        painter.setBrush(QColor(255, 235, 180, 140))
        for vx, vy in self.pending_polygon:
            sx, sy = self.world_to_screen(vx, vy)
            painter.drawEllipse(QPointF(sx, sy), 4, 4)

    def sector_world_points(self, sector: Sector) -> list[tuple[float, float]]:
        if self.map is None:
            return []

        points: list[tuple[float, float]] = []
        for vertex_index in sector.vertex_indices:
            if vertex_index < 0 or vertex_index >= len(self.map.vertexes):
                return []
            vertex = self.map.vertexes[vertex_index]
            points.append((float(vertex.x), float(vertex.y)))
        return points

    def draw_sectors(self, painter: QPainter) -> None:
        if self.map is None:
            return

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(110, 155, 180, 70))

        for sector in self.map.sectors:
            points = self.sector_world_points(sector)
            if len(points) < 3:
                continue

            polygon: list[QPointF] = []
            for wx, wy in points:
                sx, sy = self.world_to_screen(int(wx), int(wy))
                polygon.append(QPointF(sx, sy))

            painter.drawPolygon(polygon)

    def point_in_polygon(self, x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
        inside = False
        point_count = len(polygon)
        if point_count < 3:
            return False

        j = point_count - 1
        for i in range(point_count):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def find_sector_at(self, sx: float, sy: float) -> Optional[tuple[int, Sector]]:
        if self.map is None:
            return None

        wx, wy = self.screen_to_world(sx, sy)

        for index in range(len(self.map.sectors) - 1, -1, -1):
            sector = self.map.sectors[index]
            polygon = self.sector_world_points(sector)
            if self.point_in_polygon(wx, wy, polygon):
                return index, sector

        return None

    def emit_sector_info_at(self, sx: float, sy: float) -> None:
        sector_match = self.find_sector_at(sx, sy)
        if sector_match is None:
            return

        sector_index, _ = sector_match
        self.sector_selected.emit(sector_index)

    def try_close_sector(self, point: tuple[int, int]) -> bool:
        if len(self.pending_polygon) < 3:
            return False

        first_x, first_y = self.pending_polygon[0]
        px, py = point
        if abs(px - first_x) > self.grid_size // 2:
            return False
        if abs(py - first_y) > self.grid_size // 2:
            return False

        self.commit_sector_polygon()
        return True

    def commit_sector_polygon(self) -> None:
        if len(self.pending_polygon) < 3:
            return

        doom_map = self.ensure_map()
        base_vertex_index = len(doom_map.vertexes)
        sector_vertex_indices: list[int] = []

        for x, y in self.pending_polygon:
            doom_map.vertexes.append(Vertex(x, y))
            sector_vertex_indices.append(base_vertex_index)
            base_vertex_index += 1

        for i in range(len(sector_vertex_indices)):
            v1 = sector_vertex_indices[i]
            v2 = sector_vertex_indices[(i + 1) % len(sector_vertex_indices)]
            doom_map.linedefs.append(
                Linedef(v1=v1, v2=v2, flags=0, special=0, tag=0, right=-1, left=-1)
            )

        doom_map.sectors.append(Sector(vertex_indices=sector_vertex_indices))
        self.pending_polygon.clear()

    def increase_grid_size(self) -> None:
        self.grid_size *= 2
        self.update()

    def decrease_grid_size(self) -> None:
        self.grid_size = max(1, self.grid_size // 2)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        self.draw_grid(painter)

        if self.map:
            self.draw_sectors(painter)

        self.draw_grid_highlight(painter)
        self.draw_pending_polygon(painter)

        if not self.map:
            return

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

        if self.controls_manager.matches_mouse("pan_drag", event.button()):
            self.last_mouse = event.position()
            self.pan_start_mouse = event.position()
            self.is_panning = False
            self.update()
            return

        if self.controls_manager.matches_mouse("sector_draw_click", event.button()):
            point = self.nearest_grid_point(event.position().x(), event.position().y())
            if not self.try_close_sector(point):
                self.pending_polygon.append(point)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.hover_mouse = event.position()

        if self.last_mouse is None:
            self.update()
            return

        if self.pan_start_mouse is not None and not self.is_panning:
            start = self.pan_start_mouse
            if abs(event.position().x() - start.x()) > 2 or abs(event.position().y() - start.y()) > 2:
                self.is_panning = True

        pos = event.position()
        diff = pos - self.last_mouse
        self.offset_x += diff.x()
        self.offset_y += diff.y()
        self.last_mouse = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.hover_mouse = event.position()
        if self.controls_manager.matches_mouse("pan_drag", event.button()):
            if not self.is_panning:
                self.emit_sector_info_at(event.position().x(), event.position().y())
            self.last_mouse = None
            self.pan_start_mouse = None
            self.is_panning = False
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.controls_manager.matches("cancel_sector_draw", event.key()):
            self.pending_polygon.clear()
            self.update()
            return

        if self.controls_manager.matches("grid_decrease", event.key()):
            self.decrease_grid_size()
            return

        if self.controls_manager.matches("grid_increase", event.key()):
            self.increase_grid_size()
            return

        super().keyPressEvent(event)
