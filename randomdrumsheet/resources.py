import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase

_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ASSETS_DIR = _BASE_DIR / "randomdrumsheet" / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"


def load_fonts() -> list[str]:
    families = []
    for path in sorted(FONTS_DIR.glob("*.[ot]tf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            print(f"[RandomDrumSheet] 폰트를 불러오지 못했습니다: {path}", file=sys.stderr)
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families
