import math
from enum import Enum
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from controls_manager import ControlsManager
from models import DoomMap, Linedef, SectorDef, SectorRegion, Sidedef, Thing, Vertex


class EditMode(Enum):
    SECTOR = "sector"
    THING = "thing"
    LINE = "line"


class MapCanvas(QWidget):
    sector_selected = Signal(int)
    thing_selected = Signal(int)
    linedef_selected = Signal(int)
    thing_create_requested = Signal(int, int)
    mode_changed = Signal(str)

    def __init__(self, controls_manager: ControlsManager) -> None:
        super().__init__()
        self.controls_manager = controls_manager
        self.map: Optional[DoomMap] = None
        self.mode: EditMode = EditMode.SECTOR
        self.zoom: float = 0.5
        self.offset_x: float = 0
        self.offset_y: float = 0
        self.grid_size: int = 64
        self.last_mouse: Optional[QPointF] = None
        self.pan_start_mouse: Optional[QPointF] = None
        self.is_panning: bool = False
        self.hover_mouse: Optional[QPointF] = None
        self.hovered_sector_index: Optional[int] = None
        self.hovered_thing_index: Optional[int] = None
        self.hovered_linedef_index: Optional[int] = None
        self.pending_polygon: list[tuple[int, int]] = []
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(800, 600)

    def set_map(self, doom_map: DoomMap) -> None:
        self.map = doom_map
        self.pending_polygon.clear()
        self.hovered_sector_index = None
        self.hovered_thing_index = None
        self.hovered_linedef_index = None
        self.update()

    def set_mode_sector(self) -> None:
        self.mode = EditMode.SECTOR
        self.pending_polygon.clear()
        self.hovered_thing_index = None
        self.hovered_linedef_index = None
        self.mode_changed.emit(self.mode.value)
        self.update()

    def set_mode_thing(self) -> None:
        self.mode = EditMode.THING
        self.pending_polygon.clear()
        self.hovered_sector_index = None
        self.hovered_linedef_index = None
        self.mode_changed.emit(self.mode.value)
        self.update()

    def set_mode_line(self) -> None:
        self.mode = EditMode.LINE
        self.pending_polygon.clear()
        self.hovered_sector_index = None
        self.hovered_thing_index = None
        self.mode_changed.emit(self.mode.value)
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

    def sector_world_points(self, region: SectorRegion) -> list[tuple[float, float]]:
        if self.map is None:
            return []

        points: list[tuple[float, float]] = []
        for vertex_index in region.vertex_indices:
            if vertex_index < 0 or vertex_index >= len(self.map.vertexes):
                return []
            vertex = self.map.vertexes[vertex_index]
            points.append((float(vertex.x), float(vertex.y)))
        return points

    def draw_sectors(self, painter: QPainter) -> None:
        if self.map is None:
            return

        for region in self.map.sector_regions:
            points = self.sector_world_points(region)
            if len(points) < 3:
                continue

            is_hovered = region.sector_index == self.hovered_sector_index
            if is_hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(180, 210, 235, 140))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(110, 155, 180, 90))

            polygon: list[QPointF] = []
            for wx, wy in points:
                sx, sy = self.world_to_screen(int(wx), int(wy))
                polygon.append(QPointF(sx, sy))

            painter.drawPolygon(polygon)

    def draw_things(self, painter: QPainter) -> None:
        if self.map is None:
            return

        for index, thing in enumerate(self.map.things):
            self.draw_thing(painter, thing, hovered=index == self.hovered_thing_index)

    def draw_thing(self, painter: QPainter, thing: Thing, *, hovered: bool = False) -> None:
        sx, sy = self.world_to_screen(thing.x, thing.y)

        is_player_start = thing.thing_type == 1
        fill_color = QColor(255, 245, 160) if hovered and is_player_start else (
            QColor(255, 220, 120) if is_player_start else QColor(120, 220, 255)
        )
        if hovered and not is_player_start:
            fill_color = QColor(160, 240, 255)
        outline_color = QColor(40, 40, 40)

        painter.setPen(QPen(outline_color, 2 if hovered else 1))
        painter.setBrush(fill_color)
        painter.drawEllipse(QPointF(sx, sy), 7 if hovered else 5, 7 if hovered else 5)

        angle_radians = math.radians(thing.angle)
        arrow_length = 14 if hovered else 10
        arrow_x = sx + math.cos(angle_radians) * arrow_length
        arrow_y = sy - math.sin(angle_radians) * arrow_length
        painter.setPen(QPen(fill_color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(sx, sy), QPointF(arrow_x, arrow_y))

    def draw_linedefs(self, painter: QPainter) -> None:
        if self.map is None:
            return

        for index, line in enumerate(self.map.linedefs):
            if line.v1 >= len(self.map.vertexes):
                continue
            if line.v2 >= len(self.map.vertexes):
                continue

            a = self.map.vertexes[line.v1]
            b = self.map.vertexes[line.v2]
            x1, y1 = self.world_to_screen(a.x, a.y)
            x2, y2 = self.world_to_screen(b.x, b.y)

            if index == self.hovered_linedef_index:
                painter.setPen(QPen(QColor(255, 240, 170), 3))
            else:
                painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

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

    def find_sector_at(self, sx: float, sy: float) -> Optional[int]:
        if self.map is None:
            return None

        wx, wy = self.screen_to_world(sx, sy)
        matches: list[tuple[float, int]] = []

        for region in self.map.sector_regions:
            polygon = self.sector_world_points(region)
            if self.point_in_polygon(wx, wy, polygon):
                area = abs(self.polygon_area(polygon))
                matches.append((area, region.sector_index))

        if not matches:
            return None

        # Prefer the smallest containing region so nested sectors are selectable.
        matches.sort(key=lambda item: item[0])
        return matches[0][1]

    def find_thing_at(self, sx: float, sy: float, max_distance: float = 10.0) -> Optional[int]:
        if self.map is None:
            return None

        best_index: Optional[int] = None
        best_distance = max_distance
        for index, thing in enumerate(self.map.things):
            tx, ty = self.world_to_screen(thing.x, thing.y)
            distance = math.hypot(tx - sx, ty - sy)
            if distance <= best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def point_to_segment_distance(
        self,
        px: float,
        py: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> float:
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        return math.hypot(px - nearest_x, py - nearest_y)

    def find_linedef_at(self, sx: float, sy: float, max_distance: float = 8.0) -> Optional[int]:
        if self.map is None:
            return None

        best_index: Optional[int] = None
        best_distance = max_distance

        for index, line in enumerate(self.map.linedefs):
            if line.v1 >= len(self.map.vertexes):
                continue
            if line.v2 >= len(self.map.vertexes):
                continue

            a = self.map.vertexes[line.v1]
            b = self.map.vertexes[line.v2]
            x1, y1 = self.world_to_screen(a.x, a.y)
            x2, y2 = self.world_to_screen(b.x, b.y)
            distance = self.point_to_segment_distance(sx, sy, x1, y1, x2, y2)
            if distance <= best_distance:
                best_distance = distance
                best_index = index

        return best_index

    def polygon_area(self, polygon: list[tuple[float, float]]) -> float:
        if len(polygon) < 3:
            return 0.0

        area = 0.0
        for i in range(len(polygon)):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % len(polygon)]
            area += (x1 * y2) - (x2 * y1)
        return 0.5 * area

    def emit_sector_info_at(self, sx: float, sy: float) -> None:
        sector_index = self.find_sector_at(sx, sy)
        if sector_index is None:
            return

        self.sector_selected.emit(sector_index)

    def emit_thing_info_at(self, sx: float, sy: float) -> None:
        thing_index = self.find_thing_at(sx, sy)
        if thing_index is None:
            return

        self.thing_selected.emit(thing_index)

    def emit_linedef_info_at(self, sx: float, sy: float) -> None:
        linedef_index = self.find_linedef_at(sx, sy)
        if linedef_index is None:
            return

        self.linedef_selected.emit(linedef_index)

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
        sector_index = len(doom_map.sector_defs)
        doom_map.sector_defs.append(SectorDef())

        base_vertex_index = len(doom_map.vertexes)
        sector_vertex_indices: list[int] = []

        for x, y in self.pending_polygon:
            doom_map.vertexes.append(Vertex(x, y))
            sector_vertex_indices.append(base_vertex_index)
            base_vertex_index += 1

        for i in range(len(sector_vertex_indices)):
            v1 = sector_vertex_indices[i]
            v2 = sector_vertex_indices[(i + 1) % len(sector_vertex_indices)]

            sidedef_index = len(doom_map.sidedefs)
            doom_map.sidedefs.append(
                Sidedef(
                    x_offset=0,
                    y_offset=0,
                    upper_texture="",
                    lower_texture="",
                    middle_texture="",
                    sector_index=sector_index,
                )
            )

            doom_map.linedefs.append(
                Linedef(
                    v1=v1,
                    v2=v2,
                    flags=0,
                    special=0,
                    tag=0,
                    front_sidedef=sidedef_index,
                    back_sidedef=-1,
                )
            )

        doom_map.sector_regions.append(
            SectorRegion(sector_index=sector_index, vertex_indices=sector_vertex_indices)
        )
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
            self.draw_things(painter)

        self.draw_grid_highlight(painter)
        self.draw_pending_polygon(painter)

        if not self.map:
            return

        self.draw_linedefs(painter)

    def wheelEvent(self, event: QWheelEvent) -> None:
        anchor = event.position()
        world_x, world_y = self.screen_to_world(anchor.x(), anchor.y())

        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1

        # Keep the world point under the mouse fixed while zooming.
        self.offset_x = anchor.x() - (self.width() / 2) - (world_x * self.zoom)
        self.offset_y = anchor.y() - (self.height() / 2) + (world_y * self.zoom)
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
            if self.mode == EditMode.SECTOR:
                if not self.try_close_sector(point):
                    self.pending_polygon.append(point)
            elif self.mode == EditMode.THING:
                self.thing_create_requested.emit(point[0], point[1])
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.hover_mouse = event.position()
        if self.mode == EditMode.SECTOR:
            self.hovered_sector_index = self.find_sector_at(event.position().x(), event.position().y())
            self.hovered_thing_index = None
            self.hovered_linedef_index = None
        elif self.mode == EditMode.THING:
            self.hovered_sector_index = None
            self.hovered_thing_index = self.find_thing_at(event.position().x(), event.position().y())
            self.hovered_linedef_index = None
        elif self.mode == EditMode.LINE:
            self.hovered_sector_index = None
            self.hovered_thing_index = None
            self.hovered_linedef_index = self.find_linedef_at(event.position().x(), event.position().y())

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

    def leaveEvent(self, event: QEvent) -> None:
        self.hover_mouse = None
        self.hovered_sector_index = None
        self.hovered_thing_index = None
        self.hovered_linedef_index = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.hover_mouse = event.position()
        if self.controls_manager.matches_mouse("pan_drag", event.button()):
            if not self.is_panning:
                if self.mode == EditMode.SECTOR:
                    self.emit_sector_info_at(event.position().x(), event.position().y())
                elif self.mode == EditMode.THING:
                    self.emit_thing_info_at(event.position().x(), event.position().y())
                elif self.mode == EditMode.LINE:
                    self.emit_linedef_info_at(event.position().x(), event.position().y())
            self.last_mouse = None
            self.pan_start_mouse = None
            self.is_panning = False
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.controls_manager.matches("mode_sector", event.key()):
            self.set_mode_sector()
            return

        if self.controls_manager.matches("mode_thing", event.key()):
            self.set_mode_thing()
            return

        if self.controls_manager.matches("mode_line", event.key()):
            self.set_mode_line()
            return

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
