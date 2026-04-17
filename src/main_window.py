import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
    QVBoxLayout,
)

from controls_manager import ControlsManager
from editor_service import DoomEditorService
from map_canvas import MapCanvas
from models import Linedef, SectorDef, Sidedef, Thing
from thingnames import thing_name_for


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Held Doom Editor")
        self.resize(1200, 800)

        self.controls_manager = ControlsManager()
        self.canvas = MapCanvas(self.controls_manager)
        self.editor_service = DoomEditorService()
        self.canvas.set_flat_provider(self.editor_service.get_flat_image_for_current_game)
        self.actions_by_control_id: dict[str, QAction] = {}
        self.setCentralWidget(self.canvas)
        self.canvas.sector_selected.connect(self.edit_sector)
        self.canvas.sector_texture_requested.connect(self.edit_sector)
        self.canvas.thing_selected.connect(self.edit_thing)
        self.canvas.linedef_selected.connect(self.edit_linedef)
        self.canvas.linedef_texture_requested.connect(self.edit_linedef)
        self.canvas.thing_create_requested.connect(self.add_thing_at)
        self.canvas.mode_changed.connect(self.update_mode_status_label)
        self.controls_manager.binding_changed.connect(self.refresh_bound_action)
        self.loaded_status_label = QLabel()
        self.mode_status_label = QLabel()
        self.statusBar().addPermanentWidget(self.loaded_status_label)
        self.statusBar().addPermanentWidget(self.mode_status_label)

        self.build_menu()
        self.update_loaded_status_label()
        self.update_mode_status_label()

    def create_bound_action(
        self,
        action_id: str,
        callback: Callable[[], None],
    ) -> QAction:
        binding = self.controls_manager.binding(action_id)
        action = QAction(binding.label, self)
        action.setShortcut(self.controls_manager.key_sequence(action_id))
        action.triggered.connect(callback)
        self.actions_by_control_id[action_id] = action
        return action

    def refresh_bound_action(self, action_id: str) -> None:
        action = self.actions_by_control_id.get(action_id)
        if action is None:
            return

        binding = self.controls_manager.binding(action_id)
        action.setText(binding.label)
        action.setShortcut(self.controls_manager.key_sequence(action_id))

    def build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        open_action = self.create_bound_action("open_wad", self.open_wad)
        file_menu.addAction(open_action)

        save_action = self.create_bound_action("save_wad", self.save_wad)
        file_menu.addAction(save_action)

        save_as_action = self.create_bound_action("save_wad_as", self.save_wad_as)
        file_menu.addAction(save_as_action)

        open_map_action = self.create_bound_action("open_map", self.open_map)
        file_menu.addAction(open_map_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("View")

        decrease_grid_action = self.create_bound_action(
            "grid_decrease",
            self.canvas.decrease_grid_size,
        )
        view_menu.addAction(decrease_grid_action)

        increase_grid_action = self.create_bound_action(
            "grid_increase",
            self.canvas.increase_grid_size,
        )
        view_menu.addAction(increase_grid_action)

        mode_menu = self.menuBar().addMenu("Mode")

        sector_mode_action = self.create_bound_action(
            "mode_sector",
            self.canvas.set_mode_sector,
        )
        mode_menu.addAction(sector_mode_action)

        thing_mode_action = self.create_bound_action(
            "mode_thing",
            self.canvas.set_mode_thing,
        )
        mode_menu.addAction(thing_mode_action)

        line_mode_action = self.create_bound_action(
            "mode_line",
            self.canvas.set_mode_line,
        )
        mode_menu.addAction(line_mode_action)

    def update_mode_status_label(self, mode_name: str | None = None) -> None:
        if mode_name is None:
            mode_name = self.canvas.mode.value
        self.mode_status_label.setText(f"MODE: {mode_name.upper()}")

    def edit_sector(self, sector_index: int) -> None:
        if self.canvas.map is None:
            return

        if sector_index < 0 or sector_index >= len(self.canvas.map.sector_defs):
            return

        sector_def = self.canvas.map.sector_defs[sector_index]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Sector {sector_index}")

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        floor_spin = QSpinBox(dialog)
        floor_spin.setRange(-32768, 32767)
        floor_spin.setValue(sector_def.floor_height)
        form_layout.addRow("Floor Height", floor_spin)

        ceiling_spin = QSpinBox(dialog)
        ceiling_spin.setRange(-32768, 32767)
        ceiling_spin.setValue(sector_def.ceiling_height)
        form_layout.addRow("Ceiling Height", ceiling_spin)

        light_spin = QSpinBox(dialog)
        light_spin.setRange(0, 255)
        light_spin.setValue(sector_def.light_level)
        form_layout.addRow("Light Level", light_spin)

        special_spin = QSpinBox(dialog)
        special_spin.setRange(0, 32767)
        special_spin.setValue(sector_def.special_type)
        form_layout.addRow("Special Type", special_spin)

        tag_spin = QSpinBox(dialog)
        tag_spin.setRange(0, 32767)
        tag_spin.setValue(sector_def.tag)
        form_layout.addRow("Tag", tag_spin)

        flat_names = self.editor_service.list_flat_names_for_current_game()
        floor_flat_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Floor Flat",
            initial_value=sector_def.floor_texture,
            browser_names=flat_names,
            browser_title="Browse Floor Flats",
        )
        ceiling_flat_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Ceiling Flat",
            initial_value=sector_def.ceiling_texture,
            browser_names=flat_names,
            browser_title="Browse Ceiling Flats",
        )

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        sector_def.floor_height = floor_spin.value()
        sector_def.ceiling_height = ceiling_spin.value()
        sector_def.light_level = light_spin.value()
        sector_def.special_type = special_spin.value()
        sector_def.tag = tag_spin.value()
        sector_def.floor_texture = self.normalize_texture_name(floor_flat_edit.text())
        sector_def.ceiling_texture = self.normalize_texture_name(ceiling_flat_edit.text())
        self.canvas.flat_brush_cache.clear()
        self.canvas.update()

    def edit_thing(self, thing_index: int) -> None:
        if self.canvas.map is None:
            return

        if thing_index < 0 or thing_index >= len(self.canvas.map.things):
            return

        thing = self.canvas.map.things[thing_index]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Thing {thing_index}")

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        x_spin = QSpinBox(dialog)
        x_spin.setRange(-32768, 32767)
        x_spin.setValue(thing.x)
        form_layout.addRow("X", x_spin)

        y_spin = QSpinBox(dialog)
        y_spin.setRange(-32768, 32767)
        y_spin.setValue(thing.y)
        form_layout.addRow("Y", y_spin)

        angle_spin = QSpinBox(dialog)
        angle_spin.setRange(0, 359)
        angle_spin.setValue(thing.angle)
        form_layout.addRow("Angle", angle_spin)

        type_spin = QSpinBox(dialog)
        type_spin.setRange(0, 65535)
        type_spin.setValue(thing.thing_type)
        form_layout.addRow("Type", type_spin)

        flags_spin = QSpinBox(dialog)
        flags_spin.setRange(0, 65535)
        flags_spin.setValue(thing.flags)
        form_layout.addRow("Flags", flags_spin)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        thing.x = x_spin.value()
        thing.y = y_spin.value()
        thing.angle = angle_spin.value()
        thing.thing_type = type_spin.value()
        thing.flags = flags_spin.value()
        self.canvas.update()

    def thing_id_choices_from_wad(self) -> tuple[list[int], set[int], set[int]]:
        thing_ids: set[int] = set()
        wad_ids: set[int] = set()
        iwad_ids: set[int] = set()

        if self.canvas.map is not None:
            map_ids = {thing.thing_type for thing in self.canvas.map.things}
            thing_ids.update(map_ids)
            wad_ids.update(map_ids)

        if self.editor_service.has_wad_loaded():
            try:
                current_map_ids = set(self.editor_service.list_current_map_thing_ids())
                all_wad_ids = set(self.editor_service.list_wad_thing_ids())
                iwad_source_ids = set(self.editor_service.list_iwad_thing_ids_for_current_game())
                thing_ids.update(current_map_ids)
                thing_ids.update(all_wad_ids)
                thing_ids.update(iwad_source_ids)
                wad_ids.update(current_map_ids)
                wad_ids.update(all_wad_ids)
                iwad_ids.update(iwad_source_ids)
            except Exception:
                pass

        # Always include Player 1 Start as baseline placement option.
        thing_ids.add(1)
        logger.debug(
            "Thing type choices built: total=%d from_wad=%d from_iwad=%d",
            len(thing_ids),
            len(wad_ids),
            len(iwad_ids),
        )
        return sorted(thing_ids), wad_ids, iwad_ids

    def thing_label(self, thing_id: int, *, from_wad: bool, from_iwad: bool) -> str:
        game_profile = self.editor_service.current_game_profile()
        known_name = thing_name_for(game_profile, thing_id)
        if known_name is not None:
            return f"{thing_id} - {known_name}"

        if from_wad:
            return f"{thing_id} - ID {thing_id} (present in loaded WAD)"
        if from_iwad:
            return f"{thing_id} - ID {thing_id} (present in matching IWAD)"
        return f"{thing_id} - ID {thing_id}"

    def select_new_thing_settings(self) -> Optional[Thing]:
        dialog = QDialog(self)
        dialog.setWindowTitle("New Thing")

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        thing_type_combo = QComboBox(dialog)
        thing_ids, wad_ids, iwad_ids = self.thing_id_choices_from_wad()
        default_index = 0
        for index, thing_id in enumerate(thing_ids):
            if thing_id == 1:
                default_index = index
            label = self.thing_label(
                thing_id,
                from_wad=thing_id in wad_ids,
                from_iwad=thing_id in iwad_ids,
            )
            thing_type_combo.addItem(label, thing_id)
        thing_type_combo.setCurrentIndex(default_index)
        form_layout.addRow("Thing Type", thing_type_combo)

        angle_spin = QSpinBox(dialog)
        angle_spin.setRange(0, 359)
        angle_spin.setValue(0)
        form_layout.addRow("Angle", angle_spin)

        flags_spin = QSpinBox(dialog)
        flags_spin.setRange(0, 65535)
        flags_spin.setValue(7)
        form_layout.addRow("Flags", flags_spin)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            logger.debug("New Thing dialog cancelled")
            return None

        selected_thing = Thing(
            x=0,
            y=0,
            angle=angle_spin.value(),
            thing_type=int(thing_type_combo.currentData()),
            flags=flags_spin.value(),
        )
        logger.info(
            "New Thing settings chosen: type=%d angle=%d flags=%d",
            selected_thing.thing_type,
            selected_thing.angle,
            selected_thing.flags,
        )
        return selected_thing

    def add_thing_at(self, x: int, y: int) -> None:
        settings = self.select_new_thing_settings()
        if settings is None:
            return

        doom_map = self.canvas.ensure_map()
        settings.x = x
        settings.y = y
        doom_map.things.append(settings)
        logger.info(
            "Created Thing at (%d, %d): type=%d angle=%d flags=%d",
            settings.x,
            settings.y,
            settings.thing_type,
            settings.angle,
            settings.flags,
        )
        self.canvas.update()

    def edit_linedef(self, linedef_index: int) -> None:
        if self.canvas.map is None:
            return

        if linedef_index < 0 or linedef_index >= len(self.canvas.map.linedefs):
            return

        linedef = self.canvas.map.linedefs[linedef_index]
        front_index = self.ensure_linedef_sidedef(linedef, is_front=True)
        back_index = self.ensure_linedef_sidedef(linedef, is_front=False)
        front_sidedef = self.canvas.map.sidedefs[front_index]
        back_sidedef = self.canvas.map.sidedefs[back_index]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Linedef {linedef_index}")

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        vertex_max = max(0, len(self.canvas.map.vertexes) - 1)
        sidedef_max = max(0, len(self.canvas.map.sidedefs) - 1)

        v1_spin = QSpinBox(dialog)
        v1_spin.setRange(0, vertex_max)
        v1_spin.setValue(min(max(linedef.v1, 0), vertex_max))
        form_layout.addRow("Vertex 1", v1_spin)

        v2_spin = QSpinBox(dialog)
        v2_spin.setRange(0, vertex_max)
        v2_spin.setValue(min(max(linedef.v2, 0), vertex_max))
        form_layout.addRow("Vertex 2", v2_spin)

        flags_spin = QSpinBox(dialog)
        flags_spin.setRange(0, 65535)
        flags_spin.setValue(linedef.flags)
        form_layout.addRow("Flags", flags_spin)

        special_spin = QSpinBox(dialog)
        special_spin.setRange(0, 65535)
        special_spin.setValue(linedef.special)
        form_layout.addRow("Special", special_spin)

        tag_spin = QSpinBox(dialog)
        tag_spin.setRange(0, 65535)
        tag_spin.setValue(linedef.tag)
        form_layout.addRow("Tag", tag_spin)

        front_spin = QSpinBox(dialog)
        front_spin.setRange(-1, sidedef_max)
        front_spin.setValue(min(max(front_index, -1), sidedef_max))
        form_layout.addRow("Front Sidedef", front_spin)

        back_spin = QSpinBox(dialog)
        back_spin.setRange(-1, sidedef_max)
        back_spin.setValue(min(max(back_index, -1), sidedef_max))
        form_layout.addRow("Back Sidedef", back_spin)

        texture_names = self.texture_browser_names_for_linedef()
        front_upper_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Front Upper Texture",
            initial_value=front_sidedef.upper_texture,
            browser_names=texture_names,
            browser_title="Browse Front Upper",
        )
        front_middle_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Front Middle Texture",
            initial_value=front_sidedef.middle_texture,
            browser_names=texture_names,
            browser_title="Browse Front Middle",
        )
        front_lower_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Front Lower Texture",
            initial_value=front_sidedef.lower_texture,
            browser_names=texture_names,
            browser_title="Browse Front Lower",
        )
        back_upper_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Back Upper Texture",
            initial_value=back_sidedef.upper_texture,
            browser_names=texture_names,
            browser_title="Browse Back Upper",
        )
        back_middle_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Back Middle Texture",
            initial_value=back_sidedef.middle_texture,
            browser_names=texture_names,
            browser_title="Browse Back Middle",
        )
        back_lower_edit = self.add_texture_field(
            form_layout,
            dialog,
            label="Back Lower Texture",
            initial_value=back_sidedef.lower_texture,
            browser_names=texture_names,
            browser_title="Browse Back Lower",
        )

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        linedef.v1 = v1_spin.value()
        linedef.v2 = v2_spin.value()
        linedef.flags = flags_spin.value()
        linedef.special = special_spin.value()
        linedef.tag = tag_spin.value()
        linedef.front_sidedef = front_spin.value()
        linedef.back_sidedef = back_spin.value()

        if 0 <= linedef.front_sidedef < len(self.canvas.map.sidedefs):
            front_sidedef = self.canvas.map.sidedefs[linedef.front_sidedef]
            front_sidedef.upper_texture = self.normalize_texture_name(front_upper_edit.text())
            front_sidedef.middle_texture = self.normalize_texture_name(front_middle_edit.text())
            front_sidedef.lower_texture = self.normalize_texture_name(front_lower_edit.text())

        if 0 <= linedef.back_sidedef < len(self.canvas.map.sidedefs):
            back_sidedef = self.canvas.map.sidedefs[linedef.back_sidedef]
            back_sidedef.upper_texture = self.normalize_texture_name(back_upper_edit.text())
            back_sidedef.middle_texture = self.normalize_texture_name(back_middle_edit.text())
            back_sidedef.lower_texture = self.normalize_texture_name(back_lower_edit.text())
        self.canvas.update()

    def normalize_texture_name(self, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            return "-"
        return normalized[:8]

    def texture_browser_names_for_linedef(self) -> list[str]:
        names: set[str] = set(self.editor_service.list_flat_names_for_current_game())
        if self.canvas.map is not None:
            for sidedef in self.canvas.map.sidedefs:
                for tex in (sidedef.upper_texture, sidedef.middle_texture, sidedef.lower_texture):
                    normalized = self.normalize_texture_name(tex)
                    if normalized != "-":
                        names.add(normalized)
        return sorted(names)

    def add_texture_field(
        self,
        form_layout: QFormLayout,
        parent: QWidget,
        *,
        label: str,
        initial_value: str,
        browser_names: list[str],
        browser_title: str,
    ) -> QLineEdit:
        line_edit = QLineEdit(initial_value, parent)
        preview = QLabel(parent)
        preview.setFixedSize(64, 64)
        preview.setScaledContents(True)
        browse_button = QPushButton("Browse", parent)

        row_widget = QWidget(parent)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(line_edit)
        row_layout.addWidget(preview)
        row_layout.addWidget(browse_button)
        form_layout.addRow(label, row_widget)

        self.update_texture_preview(preview, line_edit.text())
        line_edit.textChanged.connect(
            lambda text, p=preview: self.update_texture_preview(p, text)
        )
        browse_button.clicked.connect(
            lambda _checked=False, edit=line_edit, names=browser_names, title=browser_title:
            self.browse_texture_name(edit, names, title)
        )
        return line_edit

    def update_texture_preview(self, preview: QLabel, texture_name: str) -> None:
        normalized = self.normalize_texture_name(texture_name)
        image = self.editor_service.get_flat_image_for_current_game(normalized)
        if image is None:
            preview.setText("N/A")
            preview.setStyleSheet("QLabel { background: #222; color: #bbb; border: 1px solid #555; }")
            preview.clear()
            return

        preview.setStyleSheet("QLabel { border: 1px solid #555; }")
        preview.setText("")
        preview.setPixmap(QPixmap.fromImage(image).scaled(64, 64))

    def browse_texture_name(
        self,
        target_edit: QLineEdit,
        names: list[str],
        title: str,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)

        texture_list = QListWidget(dialog)
        texture_list.addItems(names)
        layout.addWidget(texture_list)

        preview = QLabel(dialog)
        preview.setFixedSize(128, 128)
        preview.setScaledContents(True)
        preview.setStyleSheet("QLabel { border: 1px solid #555; background: #222; color: #bbb; }")
        layout.addWidget(preview)

        current_name = self.normalize_texture_name(target_edit.text())
        for i in range(texture_list.count()):
            if texture_list.item(i).text() == current_name:
                texture_list.setCurrentRow(i)
                break

        def refresh_preview() -> None:
            item = texture_list.currentItem()
            if item is None:
                preview.setText("N/A")
                preview.clear()
                return
            image = self.editor_service.get_flat_image_for_current_game(item.text())
            if image is None:
                preview.setText("N/A")
                preview.clear()
            else:
                preview.setText("")
                preview.setPixmap(QPixmap.fromImage(image).scaled(128, 128))

        texture_list.currentItemChanged.connect(lambda _current, _previous: refresh_preview())
        refresh_preview()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = texture_list.currentItem()
        if selected is None:
            return
        target_edit.setText(selected.text())

    def ensure_linedef_sidedef(self, linedef: Linedef, *, is_front: bool) -> int:
        if self.canvas.map is None:
            return -1

        sidedef_index = linedef.front_sidedef if is_front else linedef.back_sidedef
        if sidedef_index >= 0 and sidedef_index < len(self.canvas.map.sidedefs):
            return sidedef_index

        sector_index = 0
        opposite_index = linedef.back_sidedef if is_front else linedef.front_sidedef
        if 0 <= opposite_index < len(self.canvas.map.sidedefs):
            sector_index = self.canvas.map.sidedefs[opposite_index].sector_index
        if sector_index < 0 or sector_index >= len(self.canvas.map.sector_defs):
            sector_index = 0

        if not self.canvas.map.sector_defs:
            self.canvas.map.sector_defs.append(SectorDef())
            sector_index = 0

        self.canvas.map.sidedefs.append(
            Sidedef(
                x_offset=0,
                y_offset=0,
                upper_texture="-",
                lower_texture="-",
                middle_texture="-",
                sector_index=sector_index,
            )
        )
        new_index = len(self.canvas.map.sidedefs) - 1
        if is_front:
            linedef.front_sidedef = new_index
        else:
            linedef.back_sidedef = new_index
        return new_index

    def update_loaded_status_label(self) -> None:
        wad_name = "(none)"
        if self.editor_service.current_wad_filename:
            wad_name = Path(self.editor_service.current_wad_filename).name

        map_name = self.editor_service.current_map_name or "(none)"
        self.loaded_status_label.setText(f"WAD: {wad_name} | MAP: {map_name}")

    def select_map_name(self, map_names: list[str]) -> Optional[str]:
        selected_map, accepted = QInputDialog.getItem(
            self,
            "Select Level",
            "Choose a level:",
            map_names,
            0,
            False,
        )
        if not accepted:
            return None
        return selected_map

    def load_selected_map(self, map_name: str) -> None:
        doom_map = self.editor_service.load_map(map_name)
        self.canvas.set_map(doom_map)
        self.update_loaded_status_label()

    def open_map(self) -> None:
        if not self.editor_service.has_wad_loaded():
            self.open_wad()
            return

        try:
            map_names = self.editor_service.list_current_maps()
            selected_map = self.select_map_name(map_names)
            if selected_map is None:
                return

            self.load_selected_map(selected_map)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def open_wad(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open WAD",
            "",
            "WAD Files (*.wad)",
        )
        if not filename:
            return

        try:
            map_names: list[str] = self.editor_service.load_wad(filename)
            self.update_loaded_status_label()

            selected_map = self.select_map_name(map_names)
            if selected_map is None:
                return

            self.load_selected_map(selected_map)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def save_wad(self) -> None:
        if not self.editor_service.has_wad_loaded():
            self.save_wad_as()
            return

        try:
            output_filename = self.editor_service.save_current_map()
            self.update_loaded_status_label()
            QMessageBox.information(self, "Saved", f"Saved {output_filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def save_wad_as(self) -> None:
        if not self.editor_service.has_wad_loaded():
            QMessageBox.critical(self, "Error", "No WAD is loaded")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save WAD As",
            self.editor_service.current_wad_filename or "",
            "WAD Files (*.wad)",
        )
        if not filename:
            return

        try:
            output_filename = self.editor_service.save_current_map(filename)
            self.update_loaded_status_label()
            QMessageBox.information(self, "Saved", f"Saved {output_filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
