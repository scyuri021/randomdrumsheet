import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from randomdrumsheet import __version__
from randomdrumsheet.resources import ASSETS_DIR, load_fonts
from randomdrumsheet.storage import ensure_data_dirs
from randomdrumsheet.ui import MainWindow
from randomdrumsheet.ui import style


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RandomDrumSheet")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(ASSETS_DIR / "icon.ico")))
    load_fonts()
    ensure_data_dirs()
    app.setFont(QFont(style.FONT_FAMILY, 10))
    app.setStyleSheet(style.APP_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
