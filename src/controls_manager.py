from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence


@dataclass(frozen=True)
class ControlBinding:
    action_id: str
    label: str
    shortcut: Optional[str] = None
    key: Optional[Qt.Key] = None
    mouse_button: Optional[Qt.MouseButton] = None


class ControlsManager(QObject):
    binding_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._bindings: dict[str, ControlBinding] = {
            "open_wad": ControlBinding(
                action_id="open_wad",
                label="Open WAD",
                shortcut="Ctrl+O",
                key=Qt.Key.Key_O,
            ),
            "open_map": ControlBinding(
                action_id="open_map",
                label="Open Map",
                shortcut="Ctrl+M",
                key=Qt.Key.Key_M,
            ),
            "grid_decrease": ControlBinding(
                action_id="grid_decrease",
                label="Decrease Grid",
                shortcut="[",
                key=Qt.Key.Key_BracketLeft,
            ),
            "grid_increase": ControlBinding(
                action_id="grid_increase",
                label="Increase Grid",
                shortcut="]",
                key=Qt.Key.Key_BracketRight,
            ),
            "pan_drag": ControlBinding(
                action_id="pan_drag",
                label="Pan Drag",
                mouse_button=Qt.MouseButton.LeftButton,
            ),
            "sector_draw_click": ControlBinding(
                action_id="sector_draw_click",
                label="Draw Sector Point",
                mouse_button=Qt.MouseButton.RightButton,
            ),
            "cancel_sector_draw": ControlBinding(
                action_id="cancel_sector_draw",
                label="Cancel Sector Draw",
                shortcut="Escape",
                key=Qt.Key.Key_Escape,
            ),
        }

    def binding(self, action_id: str) -> ControlBinding:
        return self._bindings[action_id]

    def key_sequence(self, action_id: str) -> QKeySequence:
        shortcut = self.binding(action_id).shortcut
        return QKeySequence("" if shortcut is None else shortcut)

    def matches(self, action_id: str, key: int) -> bool:
        binding_key = self.binding(action_id).key
        return binding_key is not None and key == int(binding_key)

    def matches_mouse(self, action_id: str, button: Qt.MouseButton) -> bool:
        binding_button = self.binding(action_id).mouse_button
        return binding_button is not None and button == binding_button

    def update_binding(
        self,
        action_id: str,
        *,
        label: str | None = None,
        shortcut: str | None = None,
        key: Qt.Key | None = None,
        mouse_button: Qt.MouseButton | None = None,
    ) -> None:
        current = self.binding(action_id)
        updated = ControlBinding(
            action_id=current.action_id,
            label=current.label if label is None else label,
            shortcut=current.shortcut if shortcut is None else shortcut,
            key=current.key if key is None else key,
            mouse_button=current.mouse_button if mouse_button is None else mouse_button,
        )
        self._bindings[action_id] = updated
        self.binding_changed.emit(action_id)
