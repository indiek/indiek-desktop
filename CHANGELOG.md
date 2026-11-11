# Changelog

All notable changes to the IndieK Desktop App are documented here.

## Unreleased

### Added
- (DESKTOP:PACKAGING-TAURI P5) "Install ik Command…" app-menu item (macOS, Linux): writes
  `~/.local/bin/ik`, a shell launcher for the bundled `indiek-sidecar ik`, so the CLI shares the
  app's keychain access. Asks before replacing an `ik` it did not write (symlinks are replaced,
  never their targets); hints at the `PATH` line when needed. Native dialogs via
  `tauri-plugin-dialog` (Rust side only; the page still has no IPC). Rust unit tests (7 new, 12).

### Changed
- (DESKTOP:APP-ICON-HANKO) App icon set replaced with the IndieK hanko logo (regenerated with
  `tauri icon` from `logos/ik_logo_hanko.jpeg`, converted to a 1024 px PNG).

## 0.1.0 - 1 Nov 2026

### Added
- (DESKTOP:PACKAGING-TAURI P2) Tauri 2 shell scaffold: starts the API sidecar with
  `--handshake --exit-on-stdin-eof`, opens the handshake's `launch_url` (only loopback http on
  the announced port) after a splash page, stops the sidecar on exit (stdin closed, killed after
  5 s). No Tauri IPC for the page; navigation limited to the splash page and `127.0.0.1`.
  Development mode `INDIEK_DESKTOP_DEV_BACKEND` runs the API from a `fastAPI/` checkout with
  `uv`. Placeholder icon. Rust unit tests (3).
- (DESKTOP:PACKAGING-TAURI P2) Start errors name the program the shell tried to run and, in
  development builds, point at `INDIEK_DESKTOP_DEV_BACKEND`; the shell logs the UI folder it
  passes to the API. Rust unit tests (5).
- (DESKTOP:PACKAGING-TAURI P3) Frozen sidecar recipe: `sidecar/indiek_sidecar.py` (one binary,
  `indiek-sidecar serve` for the API and `indiek-sidecar ik` for the CLI), PyInstaller spec
  `sidecar/indiek-sidecar.spec` (uvicorn submodules, every keyring OS backend, package
  metadata), `pyproject.toml` (uv; `indiek-api` from `../fastAPI` until it is on PyPI,
  `indiek[cli,keychain]==1.3.0`), pytest tests of the entry point.
- (DESKTOP:PACKAGING-TAURI P3) Recipe fix: PyNaCl's `_cffi_backend` as a hidden import; the
  `indiek` pin includes the `cli` extra. First macOS build (21 MB) passes the smoke test
  (`/health`, launch link, `/`, API routes, `ik --help`, exit on stdin EOF).
- (DESKTOP:PACKAGING-TAURI P4) The sidecar is a PyInstaller folder build (`dist/indiek-sidecar/`,
  39 MB): about 0.4 s to start instead of about 12 s for the single file (the very first launch
  after install is slower while macOS checks the files). `npm run build` bundles it and the built
  web UI as app resources (`indiek-sidecar/`, `web/`); the shell runs
  `<resources>/indiek-sidecar/indiek-sidecar serve` and serves `<resources>/web` unless
  `INDIEK_API_STATIC_DIR` is set. Platform icon set. First macOS build: `IndieK.app` (64 MB) and
  `.dmg` (28 MB), unsigned; smoke test passed (`/health`, `/`, sidecar stops with the app).
- README: install and run guide (prerequisites, checkout layout, dependencies, one-line start
  command, troubleshooting table, sidecar build).
