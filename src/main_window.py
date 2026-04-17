from pathlib import Path
from typing import Callable, Optional

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Python Doom WAD Editor")
        self.resize(1200, 800)

        self.controls_manager = ControlsManager()
        self.canvas = MapCanvas(self.controls_manager)
        self.editor_service = DoomEditorService()
        self.actions_by_control_id: dict[str, QAction] = {}
        self.setCentralWidget(self.canvas)
        self.canvas.sector_selected.connect(self.edit_sector)
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

    def update_mode_status_label(self) -> None:
        self.mode_status_label.setText("MODE: SECTOR")

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
