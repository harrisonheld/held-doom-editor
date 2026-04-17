import logging
import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(pathname)s:%(lineno)d] %(message)s",
    )


def main() -> None:
    configure_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
