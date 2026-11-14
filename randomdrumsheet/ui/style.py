FONT_FAMILY = "Malgun Gothic"
BUTTON_FONT_FAMILY = "NanumSquare"

BG_COLOR = "#d9d9dd"

BUTTON_BG_COLOR = "#c4c4c6"
BUTTON_BORDER_COLOR = "#7c7c7c"
BUTTON_HOVER_BG_COLOR = "#ffffff"
BUTTON_TEXT_COLOR = "#1c1c1c"
ICON_COLOR = "#ffffff"
ICON_HOVER_COLOR = "#1c1c1c"

MENU_HOVER_COLOR = "#c4c4c6"
MENU_TEXT_COLOR = "#2b2b2b"

PALETTE_GROUP_BG = "#e9e9ec"
PALETTE_HOVER_BG = "#ffffff"
PALETTE_ACTIVE_BG = "#c4c4c6"
PALETTE_GLYPH_COLOR = "#1c1c1c"
SEPARATOR_COLOR = BUTTON_BORDER_COLOR
SCORE_BG = "#ffffff"
SCORE_INK = "#1c1c1c"

APP_STYLESHEET = f"""
QMainWindow, QWidget#central {{
    background-color: {BG_COLOR};
}}
QMenuBar {{
    background-color: {BG_COLOR};
    color: {MENU_TEXT_COLOR};
    font-size: 10pt;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 14px;
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background-color: {MENU_HOVER_COLOR};
}}
QMenu {{
    background-color: #f4f4f5;
    color: {MENU_TEXT_COLOR};
    border: 1px solid {BUTTON_BORDER_COLOR};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 28px 6px 20px;
}}
QMenu::item:selected {{
    background-color: {BG_COLOR};
}}
QMenu::separator {{
    height: 1px;
    background: #b8b8bb;
    margin: 4px 8px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px 1px 2px 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 0 2px 1px 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(60, 60, 66, 110);
    border-radius: 4px;
    min-height: 36px;
    margin: 0 2px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(60, 60, 66, 110);
    border-radius: 4px;
    min-width: 36px;
    margin: 2px 0;
}}
QScrollBar::handle:hover {{
    background: rgba(60, 60, 66, 165);
}}
QScrollBar::handle:pressed {{
    background: rgba(28, 28, 28, 200);
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
    border: none;
    background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

QFrame#presetToolbar {{
    background-color: {BG_COLOR};
    border-bottom: 2px solid {SEPARATOR_COLOR};
}}
QFrame#paletteGroup {{
    background-color: {PALETTE_GROUP_BG};
    border-radius: 6px;
}}
QFrame#paletteSeparator {{
    background-color: {SEPARATOR_COLOR};
}}
QPushButton#drumButton {{
    background: transparent;
    border: none;
    border-radius: 5px;
    color: {PALETTE_GLYPH_COLOR};
}}
QPushButton#drumButton:hover {{
    background-color: {PALETTE_HOVER_BG};
}}
QPushButton#drumButton:pressed, QPushButton#drumButton:checked {{
    background-color: {PALETTE_ACTIVE_BG};
}}
QFrame#timeSigBox {{
    background-color: #ffffff;
    border: 2px solid {SEPARATOR_COLOR};
    border-radius: 6px;
}}
QFrame#timeSigLine {{
    background-color: {PALETTE_GLYPH_COLOR};
}}
QLineEdit#timeSigField {{
    background: transparent;
    border: none;
    border-radius: 4px;
    color: {PALETTE_GLYPH_COLOR};
    selection-background-color: {PALETTE_ACTIVE_BG};
    selection-color: {PALETTE_GLYPH_COLOR};
}}
QLineEdit#timeSigField:hover {{
    background-color: {PALETTE_GROUP_BG};
}}
QLineEdit#timeSigField:focus {{
    background-color: {BG_COLOR};
}}
"""
