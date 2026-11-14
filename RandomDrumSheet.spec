import os

UNUSED_QT = {
    "opengl32sw.dll",
    "qt6quick.dll", "qt6qml.dll", "qt6qmlmeta.dll", "qt6qmlmodels.dll", "qt6qmlworkerscript.dll",
    "qt6virtualkeyboard.dll", "qtvirtualkeyboardplugin.dll",
    "qt6pdf.dll", "qpdf.dll",
    "qt6network.dll", "qnetworklistmanager.dll",
    "qcertonlybackend.dll", "qopensslbackend.dll", "qschannelbackend.dll",
    "libcrypto-3-x64.dll", "libssl-3-x64.dll",
}

a = Analysis(
    ["main.py"],
    datas=[("randomdrumsheet/assets", "randomdrumsheet/assets")],
    excludes=["tkinter", "unittest", "pydoc", "PIL", "numpy", "fontTools",
              "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf"],
)
a.binaries = [b for b in a.binaries if os.path.basename(b[0]).lower() not in UNUSED_QT]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RandomDrumSheet",
    console=False,
    icon="randomdrumsheet/assets/icon.ico",
    version="version_info.txt",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="RandomDrumSheet",
)
