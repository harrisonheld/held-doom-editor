from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMainWindow, QMessageBox

from editor_service import DoomEditorService
from map_canvas import MapCanvas


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Python Doom WAD Editor")
        self.resize(1200, 800)

        self.canvas = MapCanvas()
        self.editor_service = DoomEditorService()
        self.setCentralWidget(self.canvas)

        self.build_menu()

    def build_menu(self) -> None:
        menu = self.menuBar().addMenu("File")

        open_action = QAction("Open WAD", self)
        open_action.triggered.connect(self.open_wad)
        menu.addAction(open_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

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
            selected_map, accepted = QInputDialog.getItem(
                self,
                "Select Level",
                "Choose a level:",
                map_names,
                0,
                False,
            )
            if not accepted:
                return

            doom_map = self.editor_service.load_map(selected_map)
            self.canvas.set_map(doom_map)
            self.statusBar().showMessage(
                f"Loaded {Path(filename).name} : {selected_map}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
