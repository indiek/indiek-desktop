# Changelog

All notable changes to the IndieK Desktop App are documented here.

## Unreleased

## 0.2.0 - 13 Nov 2026

First published release: installers for macOS (Apple silicon), Windows and Linux, bundling
`indiek-api` 1.0.0, the web UI 0.5.0 and `indiek` 1.3.0 (CLI included).

### Added
- `LICENSE` file (Apache-2.0, same text as the other IndieK repositories); the licence was only declared in `package.json` and `pyproject.toml` (FOSSDOCS:LICENSE-FILES).
- (DESKTOP:PACKAGING-TAURI P5) "Install ik Command…" app-menu item (macOS, Linux): writes
  `~/.local/bin/ik`, a shell launcher for the bundled `indiek-sidecar ik`, so the CLI shares the
  app's keychain access. Asks before replacing an `ik` it did not write (symlinks are replaced,
  never their targets); hints at the `PATH` line when needed. Native dialogs via
  `tauri-plugin-dialog` (Rust side only; the page still has no IPC). Rust unit tests (7 new, 12).
- (DESKTOP:PACKAGING-TAURI P6) `web-ui.lock.json` pins the web UI release (repository, version,
  SHA-256); `scripts/fetch_web_ui.py` (standard library only) downloads
  `custom-graph-explorer-<version>-out.tar.gz`, checks its SHA-256 and unpacks it safely into
  `web-dist/`; `--from-dir` copies a local build instead, `--pin VERSION` writes a published
  release into the lock file. 27 new pytest tests.
- (DESKTOP:PACKAGING-TAURI P6) GitHub Actions: `checks.yml` (pytest, rustfmt, clippy, cargo test
  on Linux) and `release.yml` (on a version tag equal to the app version: installers built on
  macOS arm64 (app, dmg), Windows (msi, NSIS) and Ubuntu 22.04 (AppImage, deb), gathered with a
  `SHA256SUMS.txt` into one DRAFT GitHub Release the owner publishes).

### Changed
- (DESKTOP:PACKAGING-TAURI P6) README: the installer build takes the web UI from `web-dist/`
  (`scripts/fetch_web_ui.py`: pinned release, `--from-dir`, `--pin`, `SSL_CERT_FILE` tip); new
  "Continuous integration and releases" section (checks, release workflow, release process);
  Layout lists the lock file, the script, `web-dist/` and the workflows.
- (DESKTOP:PACKAGING-TAURI P6) `release.yml` can be run by hand (`workflow_dispatch`): builds
  the installers on the three OSes as workflow artifacts only (no tag check, no release).
- (DESKTOP:APP-ICON-HANKO) App icon set replaced with the IndieK hanko logo (regenerated with
  `tauri icon` from `logos/ik_logo_hanko.jpeg`, converted to a 1024 px PNG).
- (DESKTOP:PACKAGING-TAURI P6) The sidecar takes `indiek-api` from PyPI, pinned to `1.0.0`
  (first stable `indiek-api`, 2026-11-13; was `0.17.1`), instead of the local `../fastAPI` path
  source: a fresh clone (and CI) builds on its own. README explains how to bundle unreleased API
  changes for one build.
- (DESKTOP:PACKAGING-TAURI P6) The bundled web UI (`web/` resource) now comes from `web-dist/`
  (filled by `scripts/fetch_web_ui.py`) instead of the sibling `../webUI/custom-graph-explorer/out/`.
- (DESKTOP:PACKAGING-TAURI P6) Windows: the sidecar starts without a console window
  (`CREATE_NO_WINDOW`).
- (DESKTOP:PACKAGING-TAURI P7) README "Install the released app": files per OS, checksums,
  opening unsigned builds (macOS "Open Anyway" / `xattr`, Windows SmartScreen, Linux deb and
  AppImage), "Always Allow" for the keychain; full guide on indiek.org/docs/desktop.
- (DESKTOP:PACKAGING-TAURI P6) CI: the Linux apt step (`checks.yml`, `release.yml`) retries
  downloads (`Acquire::Retries=3`) and times out after 15 min, after a runner DNS outage kept the
  first manual release run stuck for 90 min.

### Fixed
- (DESKTOP:MACOS-ADHOC-SIGN) macOS: the installed app opened once, then Gatekeeper reported
  "IndieK.app is damaged". The bundle was never sealed (main binary only linker-signed, no
  `_CodeSignature/CodeResources`). `tauri.conf.json` now ad-hoc signs the whole bundle
  (`bundle.macOS.signingIdentity: "-"`), so macOS offers "Open Anyway" like any unsigned app;
  `release.yml` fails the macOS job unless `codesign --verify --deep --strict` passes.
- (DESKTOP:RELEASE-FLATTEN) `release.yml`: the release job failed at "Checksums" (`sha256sum: dmg: Is a
  directory`) because the downloaded artifacts keep their `dmg/`, `msi/`, … folders; the step now moves
  the installers up into one folder first, and fails if any folder remains.

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
