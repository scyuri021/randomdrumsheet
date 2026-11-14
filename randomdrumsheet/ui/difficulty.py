from typing import Optional

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCompleter, QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QMenu, QPushButton, QVBoxLayout)

from ..presets import PresetStore
from . import style
from .dialogs import confirm, message

FONT = QFont(style.BUTTON_FONT_FAMILY, 10)
DIALOG_FLAGS = (Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint |
                Qt.WindowCloseButtonHint)


def _button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFont(FONT)
    b.setAutoDefault(False)
    return b


class DifficultyInput(QLineEdit):

    def __init__(self, items, value: Optional[str] = None, parent=None):
        super().__init__(value or "", parent)
        self.setFont(FONT)
        self.setPlaceholderText("난이도 (선택 안 함)")
        self.setMinimumWidth(170)
        self._items = list(items)
        self._valid = value or ""
        self._model = QStringListModel(self._items)
        self.completer_ = QCompleter(self._model, self)
        self.completer_.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer_.setCompletionMode(QCompleter.PopupCompletion)
        self.completer_.setMaxVisibleItems(12)
        self.completer_.activated.connect(self._chosen)
        self.setCompleter(self.completer_)
        self.returnPressed.connect(self.validate)

    def set_items(self, items):
        self._items = list(items)
        self._model.setStringList(self._items)

    def value(self) -> Optional[str]:
        return self._valid or None

    def set_value(self, value: Optional[str]):
        self._valid = value or ""
        self.setText(self._valid)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.completer_.setCompletionPrefix("")
        self.completer_.complete()

    def _chosen(self, text: str):
        self._valid = text
        self.setText(text)

    def validate(self) -> bool:
        text = self.text().strip()
        if text and text not in self._items:
            message(self.window(), "존재하지 않는 난이도입니다")
            self.setText(self._valid)
            return False
        self._valid = text
        self.setText(text)
        return True


class NameDialog(QDialog):

    def __init__(self, parent, title: str, prompt: str, button: str, check, initial=""):
        super().__init__(parent, DIALOG_FLAGS)
        self.setWindowTitle(title)
        self._check = check
        self.result_name = None
        label = QLabel(prompt)
        label.setFont(FONT)
        self.edit = QLineEdit(initial)
        self.edit.setFont(FONT)
        self.edit.setMinimumWidth(260)
        self.edit.selectAll()
        ok = _button(button)
        ok.clicked.connect(self._accept)
        self.edit.returnPressed.connect(self._accept)
        row = QHBoxLayout()
        row.addWidget(self.edit, 1)
        row.addWidget(ok)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(row)

    def _accept(self):
        name = self.edit.text().strip()
        if not name:
            return
        error = self._check(name)
        if error:
            message(self, error)
            return
        self.result_name = name
        self.accept()


def ask_new_difficulty(parent, store: PresetStore) -> Optional[str]:
    dialog = NameDialog(parent, "난이도 추가", "새 난이도 이름을 입력하세요", "추가",
                        lambda n: "이미 존재하는 이름입니다" if n in store.difficulties() else None)
    if dialog.exec() == QDialog.Accepted:
        store.add_difficulty(dialog.result_name)
        return dialog.result_name
    return None


class DifficultyManager(QDialog):

    renamed = Signal(str, str)
    removed = Signal(str)

    def __init__(self, parent, store: PresetStore):
        super().__init__(parent, DIALOG_FLAGS)
        self.setWindowTitle("난이도 관리")
        self.store = store
        self.list = QListWidget()
        self.list.setFont(QFont(style.BUTTON_FONT_FAMILY, 11))
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        hint = QLabel("우클릭하면 메뉴 뜹니다")
        hint.setFont(FONT)
        close = _button("닫기")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.list, 1)
        layout.addLayout(bottom)
        self.resize(340, 420)
        self._reload()

    def _reload(self):
        self.list.clear()
        self.list.addItems(self.store.difficulties())

    def _menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        name = item.text()
        menu = QMenu(self)
        menu.setFont(FONT)
        menu.addAction("이름 바꾸기", lambda: self._rename(name))
        menu.addAction("삭제", lambda: self._remove(name))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def _rename(self, old: str):
        def check(new):
            if new != old and new in self.store.difficulties():
                return "이미 존재하는 이름입니다"
            return None
        dialog = NameDialog(self, "이름 바꾸기", f"'{old}'의 새 이름을 입력하세요", "바꾸기",
                            check, initial=old)
        if dialog.exec() != QDialog.Accepted or dialog.result_name == old:
            return
        new = dialog.result_name
        users = len(self.store.difficulty_users(old))
        if users and not confirm(self, f"{users}개의 프리셋이 해당 난이도 사용 중: 일괄 적용합니다"):
            return
        self.store.rename_difficulty(old, new)
        self._reload()
        self.renamed.emit(old, new)

    def _remove(self, name: str):
        users = len(self.store.difficulty_users(name))
        if users and not confirm(self, f"{users}개의 프리셋이 사용 중입니다. 그래도 삭제하시겠습니까?"):
            return
        if not confirm(self, "정말로 삭제하시겠습니까?"):
            return
        self.store.remove_difficulty(name)
        self._reload()
        self.removed.emit(name)
