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

Work in progress (DESKTOP:PACKAGING-TAURI). **There is no installer yet**: today the app runs
from source (development mode), or you can build an installer for your own computer (below).
Done: P2 shell, P3 frozen sidecar, P4 local macOS build, P5 "Install ik Command…" menu (macOS,
Linux). Next: P6 CI matrix (Windows, Linux) + version pins, P7 install docs for the released app.

## Install the released app

Not available yet. Releases will be published on this repository's GitHub Releases page
(macOS, Windows, Linux). The first builds are **not code-signed**: macOS and Windows will warn
before the first launch; the exact steps will be listed here with the first release.

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
```

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
and `uv run pytest` for the sidecar entry point.

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

`pyproject.toml` pins both Python packages exactly, from PyPI (`indiek-api==0.17.1`, then
1.0.0 with the first desktop release; `indiek[cli,keychain]==1.3.0`), so a fresh clone builds
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
  keychain prompts. Not available on Windows yet (P6).

## Build an installer (your own computer)

With the prerequisites and checkouts of "Run from source" (steps 1 to 3):

```bash
cd indiek/desktop
uv sync && uv run pyinstaller --noconfirm sidecar/indiek-sidecar.spec   # the sidecar folder
npm run build                                                           # the app + installer
```

`npm run build` copies two resources into the app (`bundle.resources` in `tauri.conf.json`):
`dist/indiek-sidecar/` and the built UI `../webUI/custom-graph-explorer/out/` (as `web/`). On
macOS the results are in `src-tauri/target/release/bundle/`: `macos/IndieK.app` and
`dmg/IndieK_<version>_<arch>.dmg`; open the `.dmg` and drag IndieK to Applications. The build is
not signed; it uses your real workspace list and signing key, and macOS asks for keychain access
the first time the new sidecar reads the key.

## Layout

```
package.json             pinned Tauri CLI (npm run dev / build / tauri)
pyproject.toml, uv.lock  the sidecar's Python environment (indiek-api, indiek, PyInstaller)
sidecar/
  indiek_sidecar.py      entry point: `serve` or `ik`
  indiek-sidecar.spec    PyInstaller recipe, folder build (hidden imports for uvicorn and keyring backends)
tests/                   pytest tests of the entry point
ui/index.html            splash page shown until the API is ready (and its error messages)
src-tauri/
  Cargo.toml, build.rs   the Rust crate
  tauri.conf.json        app id org.indiek.desktop, bundle (icons, resources), CSP of the splash page
  src/main.rs            sidecar lifecycle, handshake, navigation guard, app menu (+ unit tests)
  src/cli_install.rs     "Install ik Command…": writes the ~/.local/bin/ik launcher (+ unit tests)
  icons/                 hanko logo set (`npx tauri icon ../logos/ik_logo_hanko_1024.png`)
```
