# PyInstaller recipe for `indiek-sidecar` (DESKTOP:PACKAGING-TAURI P3).
# Build from desktop/:  uv run pyinstaller --noconfirm sidecar/indiek-sidecar.spec
# Output: dist/indiek-sidecar/ (a folder: the `indiek-sidecar` program + `_internal/`), bundled
# as the app resource `indiek-sidecar/`. A folder starts in seconds; a one-file build unpacks
# itself to a temporary folder at every launch (≈ 12 s on macOS, 2026-10-30).
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

hiddenimports = [
    # uvicorn picks its loop/protocol/lifespan implementations by name at runtime.
    *collect_submodules("uvicorn"),
    # keyring finds its OS backends through entry points; list every platform's backend.
    *collect_submodules("keyring.backends"),
    "keyring.backends.macOS",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.libsecret",
    "keyring.backends.kwallet",
    "keyring.backends.chainer",
    "keyring.backends.fail",
    # PyNaCl (signing) loads its compiled cffi backend in a way the analysis misses.
    "_cffi_backend",
]
for optional in ("secretstorage", "jeepney", "win32ctypes"):
    try:
        hiddenimports += collect_submodules(optional)
    except Exception:  # not installed on this platform
        pass

datas = [
    *collect_data_files("indiek"),
    # __version__ and keyring's backend entry points come from package metadata.
    *copy_metadata("indiek"),
    *copy_metadata("indiek-api"),
    *copy_metadata("keyring"),
]

a = Analysis(
    ["indiek_sidecar.py"],
    hiddenimports=hiddenimports,
    datas=datas,
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="indiek-sidecar",
    console=True,  # the shell talks to it over stdin/stdout
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="indiek-sidecar", upx=False)
