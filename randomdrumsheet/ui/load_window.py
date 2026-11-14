from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPen, QPixmap,
                           QShortcut)
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..notation.engraver import Engraver
from ..presets import name_error, same_file
from . import style
from .dialogs import confirm, message
from .difficulty import NameDialog
from .tag_editor import FlowLayout

FONT = QFont(style.BUTTON_FONT_FAMILY, 10)
BOLD = QFont(style.BUTTON_FONT_FAMILY, 11, QFont.Bold)
CARD_W = 300
THUMB_H = 150
TAG_STYLE = (f"QLabel {{ background: {style.PALETTE_GROUP_BG}; border: 1px solid #b0b0b4;"
             f" border-radius: 6px; padding: 1px 6px; color: {style.PALETTE_GLYPH_COLOR}; }}")
SORTS = ["최근 수정순", "이름순"]


def render_thumbnail(score, width: int, height: int, ratio: float) -> QPixmap:
    engraver = Engraver(9.0)
    layout = engraver.layout(score, 720.0)
    sp = engraver.sp
    left = layout.systems[0].x0 - sp
    right = max(s.x1 for s in layout.systems) + sp
    top = layout.systems[0].top - 8.5 * sp
    bottom = layout.systems[-1].top + 10.5 * sp
    scale = min(width / (right - left), height / (bottom - top), 1.0)
    pixmap = QPixmap(int(width * ratio), int(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QColor(style.SCORE_BG))
    painter = QPainter(pixmap)
    painter.translate((width - (right - left) * scale) / 2,
                      (height - (bottom - top) * scale) / 2)
    painter.scale(scale, scale)
    painter.translate(-left, -top)
    engraver.paint(painter, score, layout)
    painter.end()
    return pixmap


def _check_badge(parent) -> QLabel:
    size, ratio = 24, parent.devicePixelRatioF()
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1565d8"))
    p.drawEllipse(0, 0, size, size)
    p.setPen(QPen(QColor("#ffffff"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPoint(7, 12), QPoint(11, 16), QPoint(18, 8)])
    p.end()
    badge = QLabel(parent)
    badge.setPixmap(pixmap)
    badge.setFixedSize(size, size)
    badge.setStyleSheet("QLabel { border: none; background: transparent; }")
    badge.setAttribute(Qt.WA_TransparentForMouseEvents)
    return badge


def tag_label(tag: str) -> QLabel:
    label = QLabel(f"#{tag}")
    label.setFont(FONT)
    label.setStyleSheet(TAG_STYLE)
    return label


class TagPopup(QFrame):

    def __init__(self, tags, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("TagPopup { background: #ffffff; }")
        box = QWidget(self)
        flow = FlowLayout(box)
        for t in tags:
            flow.addWidget(tag_label(t))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(box)
        width = CARD_W - 20
        box.setFixedWidth(width)
        box.setFixedHeight(flow.heightForWidth(width))


class PresetCard(QFrame):
    open_requested = Signal(object)
    clicked = Signal(object)
    rename_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, path: Path, data: dict, score, parent=None):
        super().__init__(parent)
        self.path = path
        self.data = data
        self.name = data.get("name", path.stem)
        self.time_signature = data.get("time_signature", "")
        self.tags = [t for t in data.get("tags", []) if isinstance(t, str)]
        self.modified = data.get("modified", "")
        self.setObjectName("presetCard")
        self.setFixedWidth(CARD_W)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("더블클릭하여 편집")
        self.setAttribute(Qt.WA_Hover)
        self.selected = False
        self._badge = None
        self.setStyleSheet(
            "QFrame#presetCard { background: #ffffff; border: 1px solid #b8b8bb;"
            " border-radius: 8px; }"
            "QFrame#presetCard:hover { border: 2px solid #1565d8; }"
            'QFrame#presetCard[selected="true"] { background: #e8f0fc;'
            " border: 3px solid #1565d8; }")

        thumb = QLabel()
        thumb.setFixedSize(CARD_W - 16, THUMB_H)
        thumb.setPixmap(render_thumbnail(score, CARD_W - 16, THUMB_H, self.devicePixelRatioF()))
        thumb.setStyleSheet("QLabel { border: none; }")

        name = QLabel(QFontMetrics(BOLD).elidedText(self.name, Qt.ElideRight, CARD_W - 20))
        name.setFont(BOLD)
        name.setToolTip(self.name)
        name.setStyleSheet("QLabel { border: none; }")
        difficulty = data.get("difficulty") or "-"
        info = QLabel(f"박자 {self.time_signature}  ·  난이도 {difficulty}  ·  "
                      f"{data.get('measures', '?')}마디")
        info.setFont(FONT)
        info.setStyleSheet("QLabel { border: none; color: #4a4a4a; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 10)
        layout.setSpacing(6)
        layout.addWidget(thumb)
        layout.addWidget(name)
        layout.addWidget(info)
        layout.addLayout(self._tag_row())

    def _tag_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)
        available = CARD_W - 20
        plus_w = 40
        shown, used = 0, 0
        labels = [tag_label(t) for t in self.tags]
        for i, label in enumerate(labels):
            w = label.sizeHint().width() + 4
            rest_after = len(labels) - i - 1
            if used + w + (plus_w if rest_after else 0) > available:
                break
            row.addWidget(label)
            used += w
            shown += 1
        hidden = len(labels) - shown
        if hidden:
            plus = QPushButton(f"+{hidden}")
            plus.setFont(FONT)
            plus.setFixedSize(plus_w - 4, labels[0].sizeHint().height())
            plus.setCursor(Qt.PointingHandCursor)
            plus.setToolTip("태그 모두 보기")
            plus.setStyleSheet("QPushButton { border: 1px solid #b0b0b4; border-radius: 6px;"
                               " background: #ffffff; } QPushButton:hover { background: "
                               f"{style.PALETTE_GROUP_BG}; }}")
            plus.clicked.connect(lambda: self._show_all_tags(plus))
            row.addWidget(plus)
        if not labels:
            empty = QLabel("태그 없음")
            empty.setFont(FONT)
            empty.setStyleSheet("QLabel { border: none; color: #9a9a9e; }")
            row.addWidget(empty)
        row.addStretch(1)
        return row

    def _show_all_tags(self, anchor: QWidget):
        popup = TagPopup(self.tags, self)
        popup.move(anchor.mapToGlobal(QPoint(0, anchor.height() + 4)))
        popup.show()

    def set_selected(self, on: bool):
        self.selected = on
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)
        if on and self._badge is None:
            self._badge = _check_badge(self)
            self._badge.move(self.width() - 34, 10)
        if self._badge is not None:
            self._badge.setVisible(on)
            self._badge.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.path)

    menu_enabled = True

    def contextMenuEvent(self, event):
        if not self.menu_enabled:
            return
        menu = QMenu(self)
        menu.setFont(FONT)
        menu.addAction("이름 바꾸기", lambda: self.rename_requested.emit(self))
        menu.addAction("삭제", lambda: self.delete_requested.emit(self))
        menu.exec(event.globalPos())


class FilterPopup(QFrame):

    changed = Signal()

    def __init__(self, time_sigs, tags, chosen_ts: set, chosen_tags: set, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("FilterPopup { background: #ffffff; }")
        self.chosen_ts, self.chosen_tags = chosen_ts, chosen_tags
        self.ts_list = self._list(time_sigs, chosen_ts)
        self.tag_list = self._list(tags, chosen_tags, prefix="#")
        reset = QPushButton("초기화")
        reset.setFont(FONT)
        reset.clicked.connect(self._reset)

        def title(text):
            label = QLabel(text)
            label.setFont(BOLD)
            return label
        layout = QVBoxLayout(self)
        layout.addWidget(title("박자 (OR)"))
        layout.addWidget(self.ts_list)
        layout.addWidget(title("태그 (AND)"))
        layout.addWidget(self.tag_list)
        layout.addWidget(reset, 0, Qt.AlignRight)
        self.setFixedWidth(260)

    def _list(self, values, chosen: set, prefix="") -> QListWidget:
        lst = QListWidget()
        lst.setFont(FONT)
        for v in values:
            item = QListWidgetItem(prefix + v)
            item.setData(Qt.UserRole, v)
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if v in chosen else Qt.Unchecked)
            lst.addItem(item)
        if not values:
            lst.addItem("(없음)")
        row_h = max(lst.sizeHintForRow(0), 24) if lst.count() else 24
        lst.setFixedHeight(min(200, row_h * max(1, len(values)) + 8))
        lst.itemChanged.connect(self._sync)
        lst.itemClicked.connect(self._toggle)
        return lst

    def _toggle(self, item):
        if item.data(Qt.UserRole) is not None:
            item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _sync(self, *_):
        for lst, chosen in ((self.ts_list, self.chosen_ts), (self.tag_list, self.chosen_tags)):
            chosen.clear()
            for i in range(lst.count()):
                item = lst.item(i)
                if item.data(Qt.UserRole) is not None and item.checkState() == Qt.Checked:
                    chosen.add(item.data(Qt.UserRole))
        self.changed.emit()

    def _reset(self):
        for lst in (self.ts_list, self.tag_list):
            for i in range(lst.count()):
                if lst.item(i).data(Qt.UserRole) is not None:
                    lst.item(i).setCheckState(Qt.Unchecked)


class CardGrid(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.flow = FlowLayout(self, spacing=16)
        self.flow.setContentsMargins(20, 20, 20, 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self.flow.heightForWidth(self.width()))

    def refresh(self):
        self.flow.invalidate()
        self.setMinimumHeight(self.flow.heightForWidth(max(self.width(), CARD_W)))


class LoadWindow(QWidget):

    def __init__(self, parent, store_factory, open_preset, on_renamed=None, on_deleted=None,
                 pick: bool = False):
        if pick:
            super().__init__(parent)
        else:
            super().__init__(parent, Qt.Window)
        self.pick = pick
        self._on_renamed = on_renamed or (lambda *a: None)
        self._on_deleted = on_deleted or (lambda *a: None)
        self.setWindowTitle("불러오기 - RandomDrumSheet")
        self.resize(1300, 820)
        self.setMinimumSize(700, 480)
        self.setObjectName("loadWindow")
        self.setStyleSheet(f"QWidget#loadWindow {{ background: {style.BG_COLOR}; }}")
        self._store_factory = store_factory
        self._open_preset = open_preset
        self._cards = {}
        self.chosen_ts, self.chosen_tags = set(), set()
        self.select_mode = False

        self.select_button = QPushButton("선택")
        self.select_button.setFont(FONT)
        self.select_button.setCheckable(True)
        self.select_button.setMinimumWidth(70)
        self.select_button.setToolTip("선택 모드")
        self.select_button.setStyleSheet(
            f"QPushButton:checked {{ background: #1565d8; color: #ffffff; border-radius: 4px; }}")
        self.select_button.toggled.connect(self.set_select_mode)
        self.delete_button = QPushButton("삭제")
        self.delete_button.setFont(FONT)
        self.delete_button.setMinimumWidth(70)
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.hide()
        self.all_button = QPushButton("전체 선택")
        self.none_button = QPushButton("선택 해제")
        for b in (self.all_button, self.none_button):
            b.setFont(FONT)
            b.setMinimumWidth(80)
            b.setVisible(pick)
        self.all_button.clicked.connect(lambda: self._select_all(True))
        self.none_button.clicked.connect(lambda: self._select_all(False))
        if pick:
            self.select_button.hide()
        else:
            QShortcut(QKeySequence.Delete, self, self.delete_selected)
            QShortcut(QKeySequence("Esc"), self, lambda: self.select_button.setChecked(False))

        self.filter_button = QPushButton("필터")
        self.filter_button.setFont(FONT)
        self.filter_button.setMinimumWidth(80)
        self.filter_button.clicked.connect(self._show_filter)
        self.search = QLineEdit()
        self.search.setFont(FONT)
        self.search.setPlaceholderText("프리셋 이름 검색")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(420)
        self.search.textChanged.connect(self.apply)
        self.sort = QComboBox()
        self.sort.setFont(FONT)
        self.sort.addItems(SORTS)
        self.sort.currentIndexChanged.connect(self.apply)
        center = QHBoxLayout()
        center.setSpacing(8)
        center.addWidget(self.filter_button)
        center.addWidget(self.search)
        right = QHBoxLayout()
        right.addStretch(1)
        sort_label = QLabel("정렬")
        sort_label.setFont(FONT)
        right.addWidget(sort_label)
        right.addWidget(self.sort)
        left = QHBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.select_button)
        left.addWidget(self.delete_button)
        left.addWidget(self.all_button)
        left.addWidget(self.none_button)
        left.addStretch(1)
        top = QGridLayout()
        top.setContentsMargins(20, 14, 20, 6)
        top.addLayout(left, 0, 0)
        top.addLayout(center, 0, 1)
        top.addLayout(right, 0, 2)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(2, 1)

        self.grid = CardGrid()
        scroll = QScrollArea()
        scroll.setWidget(self.grid)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea, QScrollArea > QWidget > QWidget "
                             f"{{ background: {style.BG_COLOR}; }}")
        self.empty = QLabel()
        self.empty.setFont(QFont(style.BUTTON_FONT_FAMILY, 12))
        self.empty.setAlignment(Qt.AlignCenter)
        self.count = QLabel()
        self.count.setFont(FONT)
        self.count.setContentsMargins(20, 4, 20, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.empty)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.count)
        if pick:
            self.set_select_mode(True)

    def reload(self):
        store = self._store_factory()
        seen = {}
        for path, data in store.presets():
            key = str(path)
            stamp = (data.get("modified"), path.stat().st_mtime)
            cached = self._cards.get(key)
            if cached is not None and cached[0] == stamp:
                seen[key] = cached
                continue
            try:
                _, score = store.load(path)
            except (OSError, ValueError, KeyError):
                continue
            card = PresetCard(path, data, score)
            card.open_requested.connect(self._card_open)
            card.clicked.connect(self._card_clicked)
            if self.pick:
                card.menu_enabled = False
            else:
                card.rename_requested.connect(self.rename_preset)
                card.delete_requested.connect(self.delete_preset)
            seen[key] = (stamp, card)
        for key, (_, card) in self._cards.items():
            if key not in seen or seen[key][1] is not card:
                card.deleteLater()
        self._cards = seen
        self.chosen_ts &= {c.time_signature for _, c in seen.values()}
        self.chosen_tags &= {t for _, c in seen.values() for t in c.tags}
        self.apply()

    def selected_cards(self) -> list:
        return [c for _, c in self._cards.values() if c.selected and not c.isHidden()]

    def set_select_mode(self, on: bool):
        self.select_mode = on
        if self.select_button.isChecked() != on:
            self.select_button.setChecked(on)
        if not on:
            for _, card in self._cards.values():
                card.set_selected(False)
        self.delete_button.setVisible(on and not self.pick)
        self._update_counts()

    def _select_all(self, on: bool):
        for _, card in self._cards.values():
            if not card.isHidden():
                card.set_selected(on)
        self._update_counts()

    def _card_clicked(self, card: "PresetCard"):
        if self.select_mode:
            card.set_selected(not card.selected)
            self._update_counts()

    def _card_open(self, path):
        if not self.select_mode:
            self._open_preset(path)

    def delete_selected(self):
        cards = self.selected_cards()
        if not self.select_mode or not cards:
            return
        names = ", ".join(c.name for c in cards[:3]) + (f" 외 {len(cards) - 3}개"
                                                         if len(cards) > 3 else "")
        if not confirm(self, f"선택한 프리셋 {len(cards)}개를 삭제하시겠습니까?\n({names})\n"
                             "삭제한 프리셋은 되돌릴 수 없습니다.", "삭제", "취소"):
            return
        store, failed = self._store_factory(), []
        for card in cards:
            try:
                store.delete(card.path)
                self._on_deleted(card.path)
            except OSError:
                failed.append(card.name)
        if failed:
            message(self, "삭제하지 못한 프리셋이 있습니다.\n" + "\n".join(failed))
        self.reload()

    def _update_counts(self):
        cards = [c for _, c in self._cards.values()]
        visible = [c for c in cards if not c.isHidden()]
        text = f"프리셋 {len(visible)}개" + (f" / 전체 {len(cards)}개"
                                           if len(visible) != len(cards) else "")
        if self.select_mode:
            chosen = len(self.selected_cards())
            text += f"  ·  {chosen}개 선택됨"
            self.delete_button.setEnabled(chosen > 0)
            self.delete_button.setText(f"삭제 ({chosen})" if chosen else "삭제")
        self.count.setText(text)

    def rename_preset(self, card: "PresetCard"):
        store = self._store_factory()

        def check(new):
            error = name_error(new)
            if error:
                return error
            target = store.path_for(new)
            if target.exists() and not same_file(target, card.path):
                return "이미 존재하는 이름입니다"
            return None
        dialog = NameDialog(self, "이름 바꾸기", f"'{card.name}'의 새 이름을 입력하세요",
                            "바꾸기", check, initial=card.name)
        if dialog.exec() != QDialog.Accepted or dialog.result_name == card.name:
            return
        try:
            new_path = store.rename(card.path, dialog.result_name)
        except (OSError, ValueError) as e:
            message(self, f"이름을 바꾸지 못했습니다.\n{e}")
            return
        self._on_renamed(card.path, new_path, dialog.result_name)
        self.reload()

    def delete_preset(self, card: "PresetCard"):
        if not confirm(self, f"'{card.name}' 프리셋을 삭제하시겠습니까?\n삭제한 프리셋은 되돌릴 수 없습니다.",
                       "삭제", "취소"):
            return
        try:
            self._store_factory().delete(card.path)
        except OSError as e:
            message(self, f"삭제하지 못했습니다.\n{e}")
            return
        self._on_deleted(card.path)
        self.reload()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.reload()

    def apply(self):
        query = self.search.text().strip().casefold()
        cards = [c for _, c in self._cards.values()]
        visible = [c for c in cards
                   if query in c.name.casefold()
                   and (not self.chosen_ts or c.time_signature in self.chosen_ts)
                   and self.chosen_tags <= set(c.tags)]
        if self.sort.currentText() == "이름순":
            visible.sort(key=lambda c: c.name.casefold())
        else:
            visible.sort(key=lambda c: c.modified, reverse=True)

        flow = self.grid.flow
        while flow.count():
            flow.takeAt(0)
        for card in cards:
            card.setParent(self.grid)
            card.setVisible(card in visible)
            if card not in visible and card.selected:
                card.set_selected(False)
        for card in visible:
            flow.addWidget(card)
        self.grid.refresh()

        active = len(self.chosen_ts) + len(self.chosen_tags)
        self.filter_button.setText(f"필터 ({active})" if active else "필터")
        if not cards:
            self.empty.setText("저장된 프리셋이 없습니다.")
        elif not visible:
            self.empty.setText("조건에 맞는 프리셋이 없습니다.")
        self.empty.setVisible(not visible)
        self._update_counts()

    def _show_filter(self):
        cards = [c for _, c in self._cards.values()]
        time_sigs = sorted({c.time_signature for c in cards},
                           key=lambda s: tuple(int(x) for x in s.split("/")) if "/" in s else (0,))
        tags = sorted({t for c in cards for t in c.tags})
        popup = FilterPopup(time_sigs, tags, self.chosen_ts, self.chosen_tags, self)
        popup.changed.connect(self.apply)
        popup.move(self.filter_button.mapToGlobal(QPoint(0, self.filter_button.height() + 4)))
        popup.show()
