import random
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from ..generator import GenerationError, SheetOptions, generate, max_repeat_sections
from ..notation.sheet_render import PAGE_W, SheetRenderer
from ..storage import ensure_data_dirs, sheets_dir
from . import style
from .dialogs import message
from .load_window import LoadWindow

FONT = QFont(style.BUTTON_FONT_FAMILY, 10)
BOLD = QFont(style.BUTTON_FONT_FAMILY, 11, QFont.Bold)
PREVIEW_SCALE = 1.45


def _button(text: str, primary: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFont(BOLD if primary else FONT)
    b.setMinimumSize(110, 34)
    if primary:
        b.setStyleSheet("QPushButton { background: #1565d8; color: #ffffff; border-radius: 4px; }"
                        "QPushButton:hover { background: #1258bd; }")
    return b


class GenerateWindow(QWidget):
    PICK, SETTINGS, PREVIEW = range(3)

    def __init__(self, parent, store_factory):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("생성 - RandomDrumSheet")
        self.resize(1300, 880)
        self.setMinimumSize(900, 600)
        self.setObjectName("generateWindow")
        self.setStyleSheet(f"QWidget#generateWindow {{ background: {style.BG_COLOR}; }}")
        self._store_factory = store_factory
        self._picked = []
        self.result = None
        self.renderer = None

        self.picker = LoadWindow(self, store_factory, lambda p: None, pick=True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.picker)
        self.stack.addWidget(self._build_settings())
        self.stack.addWidget(self._build_preview())

        self.step_label = QLabel()
        self.step_label.setFont(BOLD)
        self.back_button = _button("이전")
        self.back_button.clicked.connect(self.back)
        self.again_button = _button("다시 생성")
        self.again_button.setToolTip("같은 설정으로 다시 무작위로 섞음")
        self.again_button.clicked.connect(self.regenerate)
        self.next_button = _button("다음", primary=True)
        self.next_button.clicked.connect(self.next)
        self.save_button = _button("저장", primary=True)
        self.save_button.clicked.connect(self.save)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 10, 20, 16)
        bottom.addWidget(self.back_button)
        bottom.addSpacing(12)
        bottom.addWidget(self.step_label)
        bottom.addStretch(1)
        bottom.addWidget(self.again_button)
        bottom.addWidget(self.next_button)
        bottom.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack, 1)
        layout.addLayout(bottom)
        self._show_step(self.PICK)

    def _build_settings(self) -> QWidget:
        page = QWidget()
        self.title_edit = QLineEdit()
        self.title_edit.setFont(FONT)
        self.title_edit.setPlaceholderText("제목 (공란일 시 제목 없이 생성)")
        self.title_edit.setMinimumWidth(360)

        self.total_spin = self._spin(1, 256, 32)
        self.total_spin.valueChanged.connect(self._update_repeat_limit)
        self.per_line_spin = self._spin(1, 8, 4)

        self.repeat_check = QCheckBox("랜덤 위치에 되돌이표 넣기")
        self.repeat_check.setFont(FONT)
        self.repeat_label = QLabel("최대 개수")
        self.repeat_label.setFont(FONT)
        self.repeat_spin = self._spin(1, 16, 1)
        self.repeat_check.toggled.connect(self._toggle_repeat)
        self._toggle_repeat(False)
        self._update_repeat_limit()
        repeat_row = QHBoxLayout()
        repeat_row.addWidget(self.repeat_check)
        repeat_row.addSpacing(16)
        repeat_row.addWidget(self.repeat_label)
        repeat_row.addWidget(self.repeat_spin)
        repeat_row.addStretch(1)

        self.each_once_check = QCheckBox("각 프리셋을 무조건 한 개씩 포함")
        self.each_once_check.setFont(FONT)
        self.each_once_check.setChecked(True)

        self.summary = QLabel()
        self.summary.setFont(FONT)
        self.summary.setStyleSheet("QLabel { color: #4a4a4a; }")

        def label(text):
            l = QLabel(text)
            l.setFont(BOLD)
            return l
        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(16)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow(label("제목"), self.title_edit)
        form.addRow(label("총 마디수"), self.total_spin)
        form.addRow(label("한 줄 마디수"), self.per_line_spin)
        form.addRow(label("도돌이표"), repeat_row)
        form.addRow(label("프리셋"), self.each_once_check)
        form.addRow("", self.summary)

        box = QFrame()
        box.setObjectName("settingsBox")
        box.setStyleSheet("QFrame#settingsBox { background: #ffffff; border: 1px solid #b8b8bb;"
                          " border-radius: 8px; }")
        box.setLayout(form)
        form.setContentsMargins(36, 30, 36, 30)
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(box)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(2)
        return page

    @staticmethod
    def _spin(lo, hi, value) -> QSpinBox:
        spin = QSpinBox()
        spin.setFont(FONT)
        spin.setRange(lo, hi)
        spin.setValue(value)
        spin.setMinimumWidth(90)
        return spin

    def _toggle_repeat(self, on: bool):
        self.repeat_label.setEnabled(on)
        self.repeat_spin.setEnabled(on)

    def _update_repeat_limit(self):
        self.repeat_spin.setMaximum(max(1, max_repeat_sections(self.total_spin.value())))

    def _build_preview(self) -> QWidget:
        page = QWidget()
        self.preview_info = QLabel()
        self.preview_info.setFont(FONT)
        self.pages_box = QWidget()
        self.pages_layout = QVBoxLayout(self.pages_box)
        self.pages_layout.setSpacing(18)
        self.pages_layout.setContentsMargins(20, 20, 20, 20)
        self.pages_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidget(self.pages_box)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: #8f8f94; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        info_row = QHBoxLayout()
        info_row.setContentsMargins(20, 10, 20, 6)
        info_row.addWidget(self.preview_info)
        layout.addLayout(info_row)
        layout.addWidget(scroll, 1)
        return page

    def _show_preview(self):
        while self.pages_layout.count():
            item = self.pages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        ratio = self.devicePixelRatioF()
        for i in range(self.renderer.page_count):
            label = QLabel()
            label.setPixmap(QPixmap.fromImage(self.renderer.page_image(i, PREVIEW_SCALE, ratio)))
            label.setFixedSize(int(PAGE_W * PREVIEW_SCALE), int(PAGE_W * PREVIEW_SCALE * 842 / 595))
            label.setStyleSheet("QLabel { border: 1px solid #6f6f74; }")
            self.pages_layout.addWidget(label, 0, Qt.AlignHCenter)
        r = self.result
        text = (f"프리셋 {len(r.order)}개 사용 · {r.options.total_measures}마디 · "
                f"한 줄 {r.options.per_line}마디 · {self.renderer.page_count}쪽")
        if r.options.repeats:
            text += f" · 도돌이표 {len(r.repeats)}개"
            limit = max_repeat_sections(len(r.order))
            if r.options.max_repeats > limit:
                text += f" (이 조합은 최대 {limit}개까지 넣을 수 있어 줄임.)"
        self.preview_info.setText(text)

    def _show_step(self, step: int):
        self.stack.setCurrentIndex(step)
        self.back_button.setVisible(step != self.PICK)
        self.again_button.setVisible(step == self.PREVIEW)
        self.next_button.setVisible(step != self.PREVIEW)
        self.save_button.setVisible(step == self.PREVIEW)
        self.step_label.setText(["1 / 3  프리셋 선택", "2 / 3  설정", "3 / 3  미리보기"][step])

    def back(self):
        self._show_step(max(self.PICK, self.stack.currentIndex() - 1))

    def next(self):
        step = self.stack.currentIndex()
        if step == self.PICK:
            cards = self.picker.selected_cards()
            if not cards:
                message(self, "선택된 프리셋이 없습니다")
                return
            store = self._store_factory()
            picked = []
            for card in cards:
                try:
                    picked.append((card.name, store.load(card.path)[1]))
                except (OSError, ValueError, KeyError):
                    message(self, f"프리셋을 읽지 못했습니다: {card.name}")
                    return
            self._picked = picked
            total = sum(len(s.measures) for _, s in picked)
            self.summary.setText(f"선택한 프리셋 {len(picked)}개 · 프리셋 총합 {total}마디")
            self._show_step(self.SETTINGS)
        elif step == self.SETTINGS:
            if self.regenerate():
                self._show_step(self.PREVIEW)

    def options(self) -> SheetOptions:
        return SheetOptions(
            title=self.title_edit.text().strip(),
            total_measures=self.total_spin.value(),
            per_line=self.per_line_spin.value(),
            each_once=self.each_once_check.isChecked(),
            repeats=self.repeat_check.isChecked(),
            max_repeats=self.repeat_spin.value(),
        )

    def regenerate(self) -> bool:
        options = self.options()
        try:
            self.result = generate(self._picked, options, random.Random())
        except GenerationError as e:
            message(self, str(e))
            return False
        self.renderer = SheetRenderer(self.result.score, options.title, options.per_line)
        self._show_preview()
        return True

    def save(self):
        if self.renderer is None:
            return
        ensure_data_dirs()
        name = re.sub(r'[\\/:*?"<>|]', "_", self.result.options.title) or "RandomDrumSheet"
        path, _ = QFileDialog.getSaveFileName(self, "악보 저장", str(sheets_dir() / f"{name}.pdf"),
                                              "PDF 파일 (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.renderer.save_pdf(path)
        except OSError as e:
            message(self, f"저장하지 못했습니다.\n{e}")
            return
        message(self, f"저장했습니다.\n{Path(path)}", QMessageBox.Information)
