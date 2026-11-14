from dataclasses import replace
from fractions import Fraction

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel,
                               QMenuBar, QMessageBox, QScrollArea, QVBoxLayout, QWidget)

from ..notation import smufl
from ..notation.model import INSTRUMENTS
from ..presets import PresetMeta, PresetStore, same_file
from . import palette_icons as icons
from . import style
from .palette import (DrumInputPanel, PaletteButton, PaletteGroup, PaletteSeparator,
                      SplitPaletteButton, TimeSignatureBox)
from .dialogs import message
from .preset_controller import PresetController
from .save_dialog import SavePresetDialog
from .score_view import ScoreView
from .shortcut_dialog import ShortcutDialog
from .shortcuts import DEFAULTS, settings as shortcut_settings, shortcut

F = Fraction

DURATIONS = [
    (icons.note(smufl.NOTE_64TH_UP), "64분음표", F(1, 64)),
    (icons.note(smufl.NOTE_32ND_UP), "32분음표", F(1, 32)),
    (icons.note(smufl.NOTE_16TH_UP), "16분음표", F(1, 16)),
    (icons.note(smufl.NOTE_8TH_UP), "8분음표", F(1, 8)),
    (icons.note(smufl.NOTE_QUARTER_UP), "4분음표", F(1, 4)),
    (icons.note(smufl.NOTE_HALF_UP), "2분음표", F(1, 2)),
    (icons.note(smufl.NOTE_WHOLE), "온음표", F(1)),
]
HAIRPINS = [
    (icons.crescendo, "점점 크게 헤어핀", "crescendo"),
    (icons.decrescendo, "점점 작게 헤어핀", "decrescendo"),
]
ARTICULATIONS = [
    (icons.sign(smufl.ART_MARCATO_ABOVE, icons.ART_SP), "마르카토", "marcato"),
    (icons.sign(smufl.ART_ACCENT_ABOVE, icons.ART_SP), "악센트", "accent"),
    (icons.sign(smufl.ART_TENUTO_ABOVE, icons.ART_SP), "테누토", "tenuto"),
    (icons.sign(smufl.ART_STACCATO_ABOVE, icons.ART_SP), "스타카토", "staccato"),
    (icons.hihat_open, "하이햇 오픈 (o)", "hihat_open"),
    (icons.hihat_closed, "하이햇 클로즈 (+)", "hihat_closed"),
]
TREMOLOS = [
    ("tremolo16", "16분 트레몰로", icons.tremolo("tremolo16")),
    ("tremolo8", "8분 트레몰로", icons.tremolo("tremolo8")),
    ("tremolo32", "32분 트레몰로", icons.tremolo("tremolo32")),
    ("tremolo64", "64분 트레몰로", icons.tremolo("tremolo64")),
    ("buzz", "버즈 롤", icons.tremolo("buzz")),
]
GRACES = [
    ("acciaccatura", "아치아카투라 (플램)", icons.grace("acciaccatura")),
    ("appoggiatura", "아포자투라", icons.grace("appoggiatura")),
    ("grace16", "16분 꾸밈음", icons.grace("grace16")),
    ("grace32", "32분 꾸밈음", icons.grace("grace32")),
]
TUPLETS = [
    ("triplet", "셋잇단음표", icons.triplet),
    ("sextuplet", "여섯잇단음표", icons.sextuplet),
]
DRUMS = ["베이스", "스네어", "크래시", "라이드", "벨",
         "하이햇", "오픈하이햇", "스몰탐", "미들탐", "플로어탐"]

OVERFLOW_TEXT = "마디 초과, 새 마디를 생성하시겠습니까?"


class PresetEditorWindow(QWidget):

    closed = Signal()
    saved = Signal()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()

    def __init__(self, parent=None, preset=None):
        super().__init__(parent, Qt.Window)
        self.editing = preset is not None
        self.resize(1420, 760)
        self.setMinimumSize(900, 480)

        self.controller = PresetController(self)
        self.controller.confirm_overflow = self._confirm_overflow
        self.controller.choose_paste_overflow = self._choose_paste_overflow
        self.score_view = ScoreView(self.controller)

        scroll = QScrollArea()
        scroll.setWidget(self.score_view)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {style.SCORE_BG}; }}")

        self.status = QLabel()
        self.status.setObjectName("presetStatus")
        self.status.setFont(QFont(style.BUTTON_FONT_FAMILY, 10))
        self.status.setContentsMargins(16, 6, 16, 6)
        self._status_timer = QTimer(self, singleShot=True, interval=4000)
        self._status_timer.timeout.connect(self.status.clear)

        self.saved_meta = PresetMeta()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self._build_toolbar())
        layout.addWidget(scroll, 1)
        layout.addWidget(self.status)

        self._connect()
        self._build_shortcuts()
        if preset is not None:
            self.saved_meta, score = preset
            self.controller.load_score(score)
        self._update_title()
        self._sync_toolbar()
        self.score_view.setFocus()

    def _build_menu(self) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("파일")
        save = QAction("저장", self)
        save.setShortcut(shortcut("preset.save"))
        save.triggered.connect(lambda: self.save(close_after=True))
        save_as = QAction("다른 이름으로 저장", self)
        save_as.triggered.connect(lambda: self.save(close_after=False))
        file_menu.addAction(save)
        file_menu.addAction(save_as)
        self.addAction(save)

        settings_menu = bar.addMenu("설정")
        notes = settings_menu.addAction("노트 설정")
        notes.triggered.connect(lambda _=False: self._show_message("아직 안만들었습니다ㅎㅎ"))
        keys = settings_menu.addAction("단축키 설정")
        keys.triggered.connect(self.open_shortcut_settings)
        return bar

    def open_shortcut_settings(self):
        ShortcutDialog(self, shortcut_settings()).exec()
        self.score_view.setFocus()

    def _update_title(self):
        if self.editing:
            self.setWindowTitle(f"프리셋 편집 - {self.saved_meta.name} - RandomDrumSheet")
        else:
            self.setWindowTitle("프리셋 만들기 - RandomDrumSheet")

    def save(self, close_after: bool):
        self.score_view._close_text_editor(commit=True)
        old_path = self.saved_meta.path
        meta = self.saved_meta if close_after else replace(self.saved_meta, path=None)
        dialog = SavePresetDialog(self, PresetStore(), self.controller.score, meta,
                                  lock_name=self.editing and close_after)
        if dialog.exec() != SavePresetDialog.Accepted or dialog.saved_meta is None:
            return
        new_path = dialog.saved_meta.path
        if close_after and old_path is not None and not same_file(old_path, new_path):
            try:
                old_path.unlink()
            except OSError:
                pass
        self.saved_meta = dialog.saved_meta
        self._update_title()
        self._show_message(f"저장했습니다: {self.saved_meta.name}")
        self.saved.emit()
        if close_after:
            self.close()

    def _buttons(self, specs, checkable=False):
        buttons = []
        for icon, tooltip, *_ in specs:
            b = PaletteButton(icon, tooltip)
            b.setCheckable(checkable)
            buttons.append(b)
        return buttons

    def _build_toolbar(self) -> QFrame:
        self.select_button = PaletteButton(icons.pointer, "선택 모드")
        self.select_button.setCheckable(True)
        self.duration_buttons = self._buttons(DURATIONS, checkable=True)
        self.duration_group = QButtonGroup(self)
        self.duration_group.setExclusive(True)
        for b in self.duration_buttons:
            self.duration_group.addButton(b)
        self.dot_button = PaletteButton(icons.dotted_note, "점 (.)")
        self.rest_button = PaletteButton(icons.sign(smufl.REST_QUARTER), "쉼표 (0)")
        self.rimshot_button = PaletteButton(icons.sign(smufl.NOTEHEAD_X, icons.NOTEHEAD_SP),
                                            "림샷")
        for b in (self.dot_button, self.rest_button, self.rimshot_button):
            b.setCheckable(True)
        self.hairpin_buttons = self._buttons(HAIRPINS)
        self.articulation_buttons = self._buttons(ARTICULATIONS)
        self.tuplet_button = SplitPaletteButton(icons.triplet, "셋잇단음표", "잇단음표 종류")
        self.tuplet_button.set_items(TUPLETS)
        self.flip_button = PaletteButton(icons.flip_direction, "방향 뒤집기")
        self.tremolo_button = SplitPaletteButton(TREMOLOS[0][2], TREMOLOS[0][1], "트레몰로 종류")
        self.tremolo_button.set_items(TREMOLOS)
        self.grace_button = SplitPaletteButton(GRACES[0][2], GRACES[0][1], "꾸밈음 종류")
        self.grace_button.set_items(GRACES)
        self.text_button = PaletteButton(icons.text_a, "텍스트")
        self.add_button = PaletteButton(icons.plus, "마디 추가")

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(PaletteGroup([self.select_button]))
        row1.addWidget(PaletteSeparator())
        row1.addWidget(PaletteGroup(self.duration_buttons))
        row1.addWidget(PaletteSeparator())
        row1.addWidget(PaletteGroup([self.dot_button, self.rest_button, self.rimshot_button]))
        row1.addWidget(PaletteSeparator())
        row1.addWidget(PaletteGroup(self.hairpin_buttons))
        row1.addStretch(1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(PaletteGroup(self.articulation_buttons))
        row2.addWidget(PaletteSeparator())
        row2.addWidget(PaletteGroup([self.tuplet_button, self.flip_button]))
        row2.addWidget(PaletteSeparator())
        row2.addWidget(PaletteGroup([self.tremolo_button, self.grace_button,
                                     self.text_button]))
        row2.addWidget(PaletteSeparator())
        row2.addWidget(self.add_button)
        row2.addStretch(1)

        rows = QVBoxLayout()
        rows.setSpacing(8)
        rows.addLayout(row1)
        rows.addLayout(row2)

        self.time_signature = TimeSignatureBox()
        self.drum_panel = DrumInputPanel(DRUMS)
        self.drum_buttons = self.drum_panel.buttons

        toolbar = QFrame()
        toolbar.setObjectName("presetToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(16)
        layout.addWidget(self.time_signature)
        layout.addLayout(rows, 1)
        layout.addWidget(PaletteSeparator(height=None, width=3))
        layout.addWidget(self.drum_panel)
        return toolbar

    def _connect(self):
        c = self.controller
        self.select_button.clicked.connect(lambda checked: c.set_select_mode(checked))
        for button, (_, _, base) in zip(self.duration_buttons, DURATIONS):
            button.clicked.connect(lambda _=False, b=base: c.set_duration(b))
        self.dot_button.clicked.connect(c.toggle_dot)
        self.rest_button.clicked.connect(c.toggle_rest)
        self.rimshot_button.clicked.connect(c.toggle_rimshot)
        for button, (_, _, kind) in zip(self.hairpin_buttons, HAIRPINS):
            button.clicked.connect(lambda _=False, k=kind: c.add_hairpin(k))
        for button, (_, _, name) in zip(self.articulation_buttons, ARTICULATIONS):
            button.clicked.connect(lambda _=False, n=name: c.toggle_articulation(n))
        self.tuplet_button.triggered.connect(lambda: c.apply_tuplet())
        self.tuplet_button.chosen.connect(c.apply_tuplet)
        self.flip_button.clicked.connect(c.flip_direction)
        self.tremolo_button.triggered.connect(lambda: c.apply_tremolo())
        self.tremolo_button.chosen.connect(c.apply_tremolo)
        self.grace_button.triggered.connect(lambda: c.apply_grace())
        self.grace_button.chosen.connect(c.apply_grace)
        self.text_button.clicked.connect(c.request_text)
        self.add_button.clicked.connect(c.add_measure)
        for name, button in self.drum_buttons.items():
            button.clicked.connect(lambda _=False, n=name: self._input_drum(n))
        self.time_signature.edited.connect(self._time_signature_edited)

        c.state_changed.connect(self._sync_toolbar)
        c.changed.connect(self._sync_toolbar)
        c.message.connect(self._show_message)
        c.alert.connect(lambda text: message(self, text))

    def _input_drum(self, name: str):
        shift = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
        self.controller.input_drum(name, add_to_chord=shift)

    def _time_signature_edited(self, numerator: int, denominator: int):
        if not self.controller.set_time_signature(numerator, denominator):
            score = self.controller.score
            self.time_signature.set_values(score.numerator, score.denominator)
        self.score_view.setFocus()

    def _build_shortcuts(self):
        c = self.controller
        keys = [(str(i + 1), lambda b=base: c.set_duration(b))
                for i, (_, _, base) in enumerate(DURATIONS)]
        keys += [
            (".", c.toggle_dot),
            ("0", c.toggle_rest),
            ("Backspace", c.delete_selection),
            ("Esc", self._escape),
            ("Ctrl+Y", c.redo),
            ("Ctrl+Shift+Z", c.redo),
        ]
        for key, slot in keys:
            QShortcut(QKeySequence(key), self, slot)

        slots = {f"drum.{key}": (lambda n=inst.name: c.input_drum(n))
                 for key, inst in INSTRUMENTS.items()}
        slots.update({
            "edit.undo": c.undo,
            "edit.copy": c.copy_selection,
            "edit.paste": c.paste,
            "edit.delete": c.delete_selection,
            "mode.select": lambda: c.set_select_mode(not c.select_mode),
            "art.hihat_open": lambda: c.toggle_articulation("hihat_open"),
            "art.hihat_closed": lambda: c.toggle_articulation("hihat_closed"),
            "mode.rimshot": c.toggle_rimshot,
        })
        self.custom_shortcuts = {}
        for action_id in DEFAULTS:
            sc = QShortcut(self)
            sc.activated.connect(slots[action_id])
            self.custom_shortcuts[action_id] = sc
        self._apply_shortcuts()
        shortcut_settings().changed.connect(self._apply_shortcuts)

    def _apply_shortcuts(self):
        for action_id, sc in self.custom_shortcuts.items():
            sc.setKey(shortcut_settings().key(action_id))

    def _escape(self):
        if self.score_view._text_editor is not None:
            self.score_view._close_text_editor(commit=False)
        else:
            self.controller.escape()

    def _sync_toolbar(self):
        c = self.controller
        self.select_button.setChecked(c.select_mode)
        for button, (_, _, base) in zip(self.duration_buttons, DURATIONS):
            if base == c.duration:
                button.setChecked(True)
        self.dot_button.setChecked(c.dot)
        self.rest_button.setChecked(c.rest_mode)
        self.rimshot_button.setChecked(c.rimshot)
        self.tremolo_button.show_item(c.tremolo_kind)
        self.grace_button.show_item(c.grace_kind)
        self.tuplet_button.show_item(c.tuplet_kind)
        score = c.score
        if (self.time_signature.numerator.value(), self.time_signature.denominator.value()) \
                != (score.numerator, score.denominator):
            self.time_signature.set_values(score.numerator, score.denominator)

    def _show_message(self, text: str):
        self.status.setText(text)
        self._status_timer.start()

    def _confirm_overflow(self) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("RandomDrumSheet")
        box.setIcon(QMessageBox.Question)
        box.setText(OVERFLOW_TEXT)
        undo = box.addButton("undo", QMessageBox.ActionRole)
        yes = box.addButton("yes", QMessageBox.ActionRole)
        box.setDefaultButton(yes)
        box.setEscapeButton(undo)
        box.exec()
        return box.clickedButton() is yes

    def _choose_paste_overflow(self) -> str:
        box = QMessageBox(self)
        box.setWindowTitle("RandomDrumSheet")
        box.setIcon(QMessageBox.Question)
        box.setText(OVERFLOW_TEXT)
        undo = box.addButton("undo", QMessageBox.ActionRole)
        truncate = box.addButton("초과분 삭제", QMessageBox.ActionRole)
        yes = box.addButton("yes", QMessageBox.ActionRole)
        box.setDefaultButton(yes)
        box.setEscapeButton(undo)
        box.exec()
        clicked = box.clickedButton()
        return "extend" if clicked is yes else "truncate" if clicked is truncate else "undo"
