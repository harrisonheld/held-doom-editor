import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from controls_manager import ControlsManager
from editor_service import DoomEditorService
from map_canvas import MapCanvas
from models import Thing
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
        self.canvas.thing_selected.connect(self.edit_thing)
        self.canvas.linedef_selected.connect(self.edit_linedef)
        self.canvas.linedef_texture_requested.connect(self.show_linedef_textures)
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
        front_spin.setValue(min(max(linedef.front_sidedef, -1), sidedef_max))
        form_layout.addRow("Front Sidedef", front_spin)

        back_spin = QSpinBox(dialog)
        back_spin.setRange(-1, sidedef_max)
        back_spin.setValue(min(max(linedef.back_sidedef, -1), sidedef_max))
        form_layout.addRow("Back Sidedef", back_spin)

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
        self.canvas.update()

    def show_linedef_textures(self, linedef_index: int) -> None:
        if self.canvas.map is None:
            return
        if linedef_index < 0 or linedef_index >= len(self.canvas.map.linedefs):
            return

        linedef = self.canvas.map.linedefs[linedef_index]
        front_desc = self.format_sidedef_textures(linedef.front_sidedef)
        back_desc = self.format_sidedef_textures(linedef.back_sidedef)

        QMessageBox.information(
            self,
            f"Linedef {linedef_index} Textures",
            f"Front sidedef ({linedef.front_sidedef}):\n{front_desc}\n\n"
            f"Back sidedef ({linedef.back_sidedef}):\n{back_desc}",
        )

    def format_sidedef_textures(self, sidedef_index: int) -> str:
        if self.canvas.map is None:
            return "(no map)"
        if sidedef_index < 0:
            return "(none)"
        if sidedef_index >= len(self.canvas.map.sidedefs):
            return "(invalid sidedef index)"

        sidedef = self.canvas.map.sidedefs[sidedef_index]
        upper = sidedef.upper_texture or "-"
        middle = sidedef.middle_texture or "-"
        lower = sidedef.lower_texture or "-"
        return f"Upper: {upper}\nMiddle: {middle}\nLower: {lower}"

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
