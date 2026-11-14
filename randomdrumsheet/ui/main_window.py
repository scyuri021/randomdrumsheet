import os
from dataclasses import replace

import shiboken6
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QMainWindow, QMessageBox,
                               QVBoxLayout, QWidget)

from .. import __version__
from ..presets import PresetMeta, PresetStore, same_file
from ..storage import ensure_data_dirs
from . import pictograms
from .dialogs import message
from .generate_window import GenerateWindow
from .load_window import LoadWindow
from .preset_window import PresetEditorWindow
from .widgets import SquareHoverButton

APP_NAME = "RandomDrumSheet"


def _alive(window) -> bool:
    return window is not None and shiboken6.isValid(window)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)
        self._preset_window = None
        self._load_window = None
        self._generate_window = None
        self._edit_windows = {}

        self._build_menus()
        self._build_central()

    def _build_menus(self):
        bar = self.menuBar()

        file_menu = bar.addMenu("파일")
        file_menu.addAction(self._action("불러오기", self.open_load_window))
        file_menu.addAction(self._action("데이터 폴더 열기", self.open_data_folder))
        file_menu.addAction(self._action("프리셋 만들기", self.create_preset))
        file_menu.addSeparator()
        file_menu.addAction(self._action("종료", self.close))

        settings_menu = bar.addMenu("설정")
        settings_menu.addAction(self._action("악보 설정...", self.open_settings))

        info_menu = bar.addMenu("정보")
        info_menu.addAction(self._action(f"{APP_NAME} 정보", self.show_about))

    def _action(self, text, slot):
        action = QAction(text, self)
        action.triggered.connect(slot)
        return action

    def _build_central(self):
        central = QWidget(self)
        central.setObjectName("central")

        self.open_button = SquareHoverButton("불러오기", pictograms.draw_folder)
        self.preset_button = SquareHoverButton("프리셋 만들기", pictograms.draw_pencil)
        self.generate_button = SquareHoverButton("생성", pictograms.draw_eighth_note)

        self.open_button.clicked.connect(self.open_load_window)
        self.preset_button.clicked.connect(self.create_preset)
        self.generate_button.clicked.connect(self.generate)

        row = QHBoxLayout()
        row.setSpacing(40)
        row.addStretch(1)
        for button in (self.open_button, self.preset_button, self.generate_button):
            row.addWidget(button)
        row.addStretch(1)

        column = QVBoxLayout(central)
        column.addStretch(1)
        column.addLayout(row)
        column.addStretch(1)

        self.setCentralWidget(central)

    @staticmethod
    def _bring_up(window):
        window.show()
        window.raise_()
        window.activateWindow()

    def open_data_folder(self):
        path = ensure_data_dirs()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, APP_NAME, f"폴더를 열지 못했습니다.\n{path}")

    def open_load_window(self):
        if not _alive(self._load_window):
            self._load_window = LoadWindow(self, PresetStore, self.edit_preset,
                                           self._preset_renamed, self._preset_deleted)
            self._load_window.setAttribute(Qt.WA_DeleteOnClose)
        self._load_window.reload()
        self._bring_up(self._load_window)

    def create_preset(self):
        if not _alive(self._preset_window):
            self._preset_window = PresetEditorWindow(self)
            self._preset_window.setAttribute(Qt.WA_DeleteOnClose)
            self._preset_window.closed.connect(self._on_preset_window_closed)
        self._bring_up(self._preset_window)

    def _on_preset_window_closed(self):
        self._preset_window = None

    def edit_preset(self, path):
        key = os.path.normcase(str(path))
        window = self._edit_windows.get(key)
        if _alive(window):
            self._bring_up(window)
            return
        try:
            data, score = PresetStore().load(path)
        except (OSError, ValueError, KeyError) as e:
            message(self, f"프리셋을 불러오지 못했습니다.\n{e}")
            return
        meta = PresetMeta(data.get("name", path.stem), data.get("difficulty"),
                          list(data.get("tags", [])), path)
        window = PresetEditorWindow(self, preset=(meta, score))
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.closed.connect(lambda w=window: self._forget(w))
        window.saved.connect(lambda w=window: self._on_preset_saved(w))
        self._edit_windows[key] = window
        self._bring_up(window)

    def _forget(self, window):
        for k in [k for k, w in self._edit_windows.items() if w is window]:
            del self._edit_windows[k]

    def _on_preset_saved(self, window):
        self._forget(window)
        if window.isVisible() and window.saved_meta.path is not None:
            self._edit_windows[os.path.normcase(str(window.saved_meta.path))] = window
        if _alive(self._load_window):
            self._load_window.reload()

    def _windows_for(self, path):
        windows = [w for w in list(self._edit_windows.values()) + [self._preset_window]
                   if _alive(w)]
        return [w for w in windows if same_file(w.saved_meta.path, path)]

    def _preset_renamed(self, old_path, new_path, new_name):
        for window in self._windows_for(old_path):
            window.saved_meta = replace(window.saved_meta, name=new_name, path=new_path)
            window._update_title()
            if window.editing:
                self._forget(window)
                self._edit_windows[os.path.normcase(str(new_path))] = window

    def _preset_deleted(self, path):
        for window in self._windows_for(path):
            window.saved_meta = replace(window.saved_meta, path=None)
            window._show_message("이 프리셋 파일이 삭제되었습니다. 저장하면 다시 만들어집니다.")
            self._forget(window)

    def generate(self):
        if not _alive(self._generate_window):
            self._generate_window = GenerateWindow(self, PresetStore)
            self._generate_window.setAttribute(Qt.WA_DeleteOnClose)
        self._generate_window.picker.reload()
        self._bring_up(self._generate_window)

    def open_settings(self):
        pass

    def show_about(self):
        QMessageBox.about(
            self, f"{APP_NAME} 정보",
            f"<b>{APP_NAME}</b><br>"
            f"beta ver. {__version__}",
        )
