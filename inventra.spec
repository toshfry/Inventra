# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import os

block_cipher = None

ctk_datas = collect_data_files("customtkinter")

# Include the web/ folder so Flask can serve index.html
web_datas = [
    (os.path.join("web", "index.html"), "web"),
]

# Bundle brand assets (the logo shown on the activation & login screens, loaded
# via resource_path("assets/logo.png")). Without this the .exe still runs, but
# the logo silently falls back to plain text — so it must be included.
assets_datas = [
    (os.path.join("assets", f), "assets")
    for f in os.listdir("assets")
    if os.path.isfile(os.path.join("assets", f))
] if os.path.isdir("assets") else []

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("icon.ico", "."),
        *ctk_datas,
        *web_datas,
        *assets_datas,
    ],
    hiddenimports=[
        # Core
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "sqlalchemy.ext.declarative",
        "pydantic",
        "pydantic_core",
        "customtkinter",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.colorchooser",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        # Database models
        "database.models.part",
        "database.models.category",
        "database.models.supplier",
        "database.models.stock_in",
        "database.models.stock_out",
        "database.models.audit_log",
        "database.models.user",
        # App modules
        "utils.backup",
        "web_server",
        "core.licensing.license_manager",
        "ui.activation",
        "cryptography",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.primitives.asymmetric",
        "cryptography.hazmat.primitives.asymmetric.ed25519",
        *collect_submodules("cryptography"),
        # Flask / Werkzeug (for embedded web server)
        "flask",
        "flask.json",
        "flask.templating",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.routing",
        "werkzeug.exceptions",
        "werkzeug.middleware.shared_data",
        "jinja2",
        "jinja2.ext",
        "click",
        "itsdangerous",
        # SQLAlchemy & Pydantic submodules
        *collect_submodules("sqlalchemy"),
        *collect_submodules("customtkinter"),
        *collect_submodules("flask"),
        *collect_submodules("werkzeug"),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy", "IPython", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Inventra",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="icon.ico",          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version_info={
        "FileVersion":    "1, 1, 17, 0",
        "ProductVersion": "1, 1, 17, 0",
        "FileDescription": "Inventra Automotive Inventory v1.1.17",
        "ProductName":     "Inventra",
        "CompanyName":     "AutoShop Solutions",
        "LegalCopyright":  "AutoShop Solutions",
    },
)
