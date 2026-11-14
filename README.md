# IndieK Desktop

The IndieK Desktop App (FOSS, Apache-2.0): a [Tauri 2](https://tauri.app) shell around the
local IndieK API (`indiek-api`) and the IndieK web UI. It is a **distribution repository**: it
contains no component code and consumes released versions of the `indiek` SDK/CLI, the API and
the built UI (design: `project_management/Design.md`, "Repository setup after the Tauri bundle"
and "Desktop seams", 2026-10-30).

```
IndieK.app ── starts ──► sidecar: indiek_api --handshake --exit-on-stdin-eof   (127.0.0.1, random port)
    │                        │ prints {"indiek_api", "port", "launch_url"} on stdout
    └── window: splash (ui/index.html) ── navigates to launch_url ──► web UI served by the sidecar
```

- The page shown in the window is served by the sidecar and gets **no Tauri IPC** (no
  capabilities are granted); the window may only navigate to the splash page and `127.0.0.1`.
- Quitting the app closes the sidecar's stdin, which stops it (killed after 5 s otherwise); if the
  app crashes, the OS closes the pipe and the sidecar stops too.

## Status

**0.2.0 is released** (13 Nov 2026), the first published version: installers for macOS (Apple
silicon), Windows and Linux, bundling `indiek-api` 1.0.0, the web UI 0.5.0 and `indiek` 1.3.0
(CLI included). The installers are **not code-signed** yet (see below).

Not yet available: code signing (macOS notarization, Windows), Intel Mac builds, the
"Install ik Command…" menu on Windows, and in-app updates (install the new version over the old
one).

## Install the released app

Download the installer for your system from the
[latest release](https://github.com/indiek/indiek-desktop/releases/latest). Full user guide
(download, first launch, author key, keychain, update, uninstall, troubleshooting):
**[indiek.org/docs/desktop](https://indiek.org/docs/desktop/)**.

| System | File |
| --- | --- |
| macOS, Apple silicon | `IndieK_<version>_aarch64.dmg` (Intel Macs: not yet) |
| Windows 10/11, 64-bit | `IndieK_<version>_x64-setup.exe` or `IndieK_<version>_x64_en-US.msi` |
| Linux, 64-bit | `IndieK_<version>_amd64.deb` (Debian, Ubuntu) or `IndieK_<version>_amd64.AppImage` |

Check a download against the release's `SHA256SUMS.txt`. The first builds are **not
code-signed**, so confirm once that you trust the app:

- **macOS 15+**: open the app once (it is refused), then **System Settings → Privacy &
  Security → Open Anyway**, and confirm. If macOS says the app "is damaged", run
  `xattr -dr com.apple.quarantine /Applications/IndieK.app`. When asked for keychain access,
  choose **Always Allow** (asked again after each update while builds are unsigned).
- **Windows**: on *Windows protected your PC* (SmartScreen), **More info → Run anyway**.
- **Linux**: `sudo apt install ./IndieK_<version>_amd64.deb`, or `chmod +x` the AppImage and
  run it (may need `libfuse2`).

## Run from source (development mode)

### 1. Prerequisites (install them yourself, once)

| Tool | Check with | Install |
| --- | --- | --- |
| Rust ≥ 1.77.2 | `cargo --version` | [rustup](https://rustup.rs), then `source ~/.cargo/env` in each new terminal (or restart it) |
| Node.js + npm | `node --version` | [nodejs.org](https://nodejs.org) |
| `uv` | `uv --version` | [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Xcode command-line tools (macOS) | `xcode-select -p` | `xcode-select --install` |
| Linux only: WebKitGTK and friends | | see [Tauri's Linux prerequisites](https://tauri.app/start/prerequisites/#linux) |

### 2. Get the three checkouts side by side

The commands below assume this layout (one parent folder):

```
indiek/
  desktop/                        this repository
  fastAPI/                        the API (indiek-api)
  webUI/custom-graph-explorer/    the web UI
```

### 3. Install the dependencies (once, and after each pull)

```bash
cd indiek/desktop
npm install                                              # the Tauri CLI (pinned in package.json)
(cd ../webUI/custom-graph-explorer && npm ci && npm run build)   # builds the UI into out/
uv run python scripts/fetch_web_ui.py --from-dir ../webUI/custom-graph-explorer/out   # copies it into web-dist/
```

The last line is only needed to build an installer or to run the Rust checks (they expect a
`web-dist/` folder); `npm run dev` below serves the UI straight from `out/`.

The first `npm run dev` also downloads and compiles the Rust crates (a few minutes, once).

### 4. Start the app

From `indiek/desktop/`, **on one line** (variables written on separate lines without
`export` do not reach the app):

```bash
INDIEK_DESKTOP_DEV_BACKEND="$PWD/../fastAPI" INDIEK_API_STATIC_DIR="$PWD/../webUI/custom-graph-explorer/out" npm run dev
```

A window opens with "Starting the local IndieK server…", then the graph explorer. The terminal shows the shell's and
the API's log. Quit the app normally (⌘Q / closing the window): the API stops with it.

- `INDIEK_DESKTOP_DEV_BACKEND` (development only): run the API from that `fastAPI/` checkout
  with `uv` (`uv run --directory <it> python -m indiek_api`) instead of the bundled sidecar.
- `INDIEK_API_STATIC_DIR`: the built UI the API serves.
- Every other `INDIEK_API_*` / `IK_*` variable reaches the API unchanged (see the API's
  README). Your real data is used: the workspace list in `~/.indiek/workspaces.json`, and the
  signing key from `fastAPI/.env` or the OS keychain. To try things out with a separate
  workspace list, add `INDIEK_API_REGISTRY=/tmp/ik-registry.json` to the line.

### 5. If something goes wrong

| What you see | Cause and fix |
| --- | --- |
| "The IndieK server could not be started (…indiek-sidecar): No such file or directory" | `INDIEK_DESKTOP_DEV_BACKEND` did not reach the app: put it on the same line as `npm run dev` (step 4). |
| "…could not be started (uv): …" | `uv` is not on the `PATH` of this terminal. |
| `{"detail":"Not Found"}` in the window | The API has no UI to serve. The terminal line `IndieK UI folder: …` shows what it received: build the UI (step 3) or fix `INDIEK_API_STATIC_DIR`. |
| "The IndieK server stopped before it was ready" | The API failed at startup; its error is in the terminal. |
| `cargo: command not found` | Run `source ~/.cargo/env` or open a new terminal after installing Rust. |

Checks for contributors: `cd src-tauri && cargo fmt --check && cargo clippy --all-targets && cargo test`,
and `uv run pytest` for the sidecar entry point and the web UI fetcher. CI runs the same checks
on every push (see "Continuous integration and releases").

## The sidecar (`indiek-sidecar`)

The released app does not need Python: it ships one frozen binary that holds the API and the
`ik` command line, so the app and the bundled `ik` are the same program for the OS keychain:

```bash
indiek-sidecar serve [ARGS]   # = python -m indiek_api [ARGS]
indiek-sidecar ik [ARGS]      # = ik [ARGS]
```

Build it from `desktop/` (PyInstaller is in the `uv` dev group):

```bash
uv sync
uv run pytest
uv run pyinstaller --noconfirm sidecar/indiek-sidecar.spec    # → dist/indiek-sidecar/
```

It is a folder (the program plus `_internal/`), not a single file: it starts in about 0.4 s
instead of about 12 s. The first launch after an install or update is slower (about 15 s on
macOS) while the OS checks the new files.

`pyproject.toml` pins both Python packages exactly, from PyPI (`indiek-api==1.0.0`,
`indiek[cli,keychain]==1.3.0`), so a fresh clone builds
on its own and the sidecar ships exactly what was tested. To bundle unreleased API changes from a
sibling `fastAPI/` checkout, install it over the pin for that build only:
`uv pip install -e ../fastAPI` after `uv sync` (the next `uv sync` restores the pin), or add a
temporary `[tool.uv.sources] indiek-api = { path = "../fastAPI" }` that is never committed.
On macOS, every newly built (unsigned) sidecar asks for keychain access the first time it reads
the signing key.

## Command-line `ik`

The app menu (**IndieK → Install ik Command…** on macOS) puts the bundled CLI on your command
line: it writes `~/.local/bin/ik`, a two-line shell launcher that runs
`<app>/…/indiek-sidecar ik "$@"`. No administrator password is needed.

- If `~/.local/bin` is not on your `PATH`, the dialog says so; add
  `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc` (or your shell's profile).
- If `~/.local/bin/ik` already exists and was not written by the app (for example
  `uv tool install indiek`), the app asks before replacing it (a symlink is replaced, never the
  file it points to). A launcher written by the app is replaced silently: choose the menu item
  again after moving the app.
- The CLI and the app are the same binary, so `ik` uses the app's signing key without extra
  keychain prompts. Not available on Windows yet.

## Build an installer (your own computer)

With the prerequisites and checkouts of "Run from source" (steps 1 to 3):

```bash
cd indiek/desktop
uv sync && uv run pyinstaller --noconfirm sidecar/indiek-sidecar.spec   # the sidecar folder
uv run python scripts/fetch_web_ui.py                                   # the web UI (see below)
npm run build                                                           # the app + installer
```

`npm run build` copies two resources into the app (`bundle.resources` in `tauri.conf.json`):
`dist/indiek-sidecar/` and the built UI `web-dist/` (as `web/`). On macOS the results are in
`src-tauri/target/release/bundle/`: `macos/IndieK.app` and `dmg/IndieK_<version>_<arch>.dmg`;
open the `.dmg` and drag IndieK to Applications. The build is not signed; it uses your real
workspace list and signing key, and macOS asks for keychain access the first time the new
sidecar reads the key.

### The web UI (`web-ui.lock.json`, `scripts/fetch_web_ui.py`)

`web-dist/` is not committed. `web-ui.lock.json` pins the web UI release the app ships
(repository `indiek/indiek-webui`, version, SHA-256 of the tarball); the script fills
`web-dist/` (standard library only, no extra dependency):

| Command (from `desktop/`) | What it does |
| --- | --- |
| `uv run python scripts/fetch_web_ui.py` | downloads `custom-graph-explorer-<version>-out.tar.gz` from the pinned GitHub Release, checks its SHA-256 against the lock file and unpacks it into `web-dist/` |
| `uv run python scripts/fetch_web_ui.py --from-dir ../webUI/custom-graph-explorer/out` | copies a local UI build instead (to try unreleased UI changes; never used by CI) |
| `uv run python scripts/fetch_web_ui.py --pin X.Y.Z` | moves the pin to a published UI release: writes its version and SHA-256 into `web-ui.lock.json` (commit that file) |

If the download fails with `CERTIFICATE_VERIFY_FAILED` (the python.org installer for macOS
ships without CA certificates), put `SSL_CERT_FILE=/etc/ssl/cert.pem` in front of the command.

## Continuous integration and releases

Two GitHub Actions workflows live in `.github/workflows/`:

- `checks.yml`, on every push and pull request (Ubuntu 22.04): pytest, `cargo fmt --check`,
  `cargo clippy` (warnings are errors) and `cargo test`.
- `release.yml`, on a pushed version tag (`X.Y.Z`): builds the sidecar, fetches the pinned web
  UI and builds the installers on three runners — macOS arm64 (`.app`, `.dmg`), Windows (`.msi`,
  NSIS `.exe`) and Ubuntu 22.04 (`.AppImage`, `.deb`) — then gathers them with a
  `SHA256SUMS.txt` into **one draft** GitHub Release. It can also be started by hand
  (Actions tab → **Release desktop app** → **Run workflow**) to try the builds without a tag:
  the installers are then only attached to the run as artifacts, with no version check and no
  release.

Release process:

1. Set the same new version in `package.json`, `src-tauri/tauri.conf.json` and
   `src-tauri/Cargo.toml`, and move the CHANGELOG "Unreleased" entries under it. The workflow
   stops if the tag differs from any of the three. Keep `pyproject.toml`'s version in step too
   (not checked by the workflow).
2. Commit, tag `X.Y.Z` (no `v` prefix) and push the tag.
3. When `release.yml` is green, download and try the installers from the draft release, then
   publish it on GitHub.

## Layout

```
package.json             pinned Tauri CLI (npm run dev / build / tauri)
pyproject.toml, uv.lock  the sidecar's Python environment (indiek-api, indiek, PyInstaller)
web-ui.lock.json         pinned web UI release (repository, version, SHA-256)
scripts/fetch_web_ui.py  fills web-dist/ from the pinned release or a local build
web-dist/                the web UI bundled into the app (generated, not committed)
sidecar/
  indiek_sidecar.py      entry point: `serve` or `ik`
  indiek-sidecar.spec    PyInstaller recipe, folder build (hidden imports for uvicorn and keyring backends)
tests/                   pytest tests of the entry point and the web UI fetcher
ui/index.html            splash page shown until the API is ready (and its error messages)
src-tauri/
  Cargo.toml, build.rs   the Rust crate
  tauri.conf.json        app id org.indiek.desktop, bundle (icons, resources), CSP of the splash page
  src/main.rs            sidecar lifecycle, handshake, navigation guard, app menu (+ unit tests)
  src/cli_install.rs     "Install ik Command…": writes the ~/.local/bin/ik launcher (+ unit tests)
  icons/                 hanko logo set (`npx tauri icon ../logos/ik_logo_hanko_1024.png`)
.github/workflows/
  checks.yml             tests, format and lint on every push
  release.yml            installers for macOS, Windows, Linux → draft GitHub Release
```

## License

Apache License 2.0: see [`LICENSE`](LICENSE).
