from PySide6.QtWidgets import QMessageBox

TITLE = "RandomDrumSheet"


def message(parent, text: str, icon=QMessageBox.Warning):
    box = QMessageBox(icon, TITLE, text, parent=parent)
    ok = box.addButton("확인", QMessageBox.ActionRole)
    box.setDefaultButton(ok)
    box.setEscapeButton(ok)
    box.exec()


def confirm(parent, text: str, ok_text: str = "확인", cancel_text: str = "취소",
            icon=QMessageBox.Question) -> bool:
    box = QMessageBox(icon, TITLE, text, parent=parent)
    ok = box.addButton(ok_text, QMessageBox.ActionRole)
    cancel = box.addButton(cancel_text, QMessageBox.ActionRole)
    box.setDefaultButton(ok)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is ok
