"""Put the built IndieK web UI into `web-dist/` for the desktop bundle (DESKTOP:PACKAGING-TAURI P6).

The web UI (custom-graph-explorer) publishes its static export on its GitHub Release as
`custom-graph-explorer-<version>-out.tar.gz` plus a `.sha256` file. `web-ui.lock.json` pins
the repository, version and SHA-256 that this app ships; `tauri.conf.json` bundles
`web-dist/` as the `web/` resource.

    uv run python scripts/fetch_web_ui.py                 # download, verify, unpack (CI)
    uv run python scripts/fetch_web_ui.py --from-dir ../webUI/custom-graph-explorer/out
    uv run python scripts/fetch_web_ui.py --pin 0.6.0     # pin a release in the lock file

Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOCK = DESKTOP_DIR / "web-ui.lock.json"
DEFAULT_DEST = DESKTOP_DIR / "web-dist"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
DOWNLOAD_TIMEOUT_S = 120


class FetchError(Exception):
    """A problem the user must fix; printed without a traceback."""


@dataclass(frozen=True)
class WebUiLock:
    repository: str
    version: str
    sha256: str


def tarball_name(version: str) -> str:
    return f"custom-graph-explorer-{version}-out.tar.gz"


def release_url(repository: str, version: str, filename: str) -> str:
    return f"https://github.com/{repository}/releases/download/{version}/{filename}"


def _validated(repository: object, version: object, lock_path: Path) -> tuple[str, str]:
    if not isinstance(repository, str) or not REPOSITORY_RE.match(repository):
        raise FetchError(
            f"{lock_path}: 'repository' must look like 'owner/name', got {repository!r}"
        )
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise FetchError(f"{lock_path}: 'version' must look like '1.2.3', got {version!r}")
    return repository, version


def read_lock(lock_path: Path) -> WebUiLock:
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FetchError(f"Lock file not found: {lock_path}") from None
    except json.JSONDecodeError as exc:
        raise FetchError(f"{lock_path} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise FetchError(f"{lock_path} must contain a JSON object")
    repository, version = _validated(data.get("repository"), data.get("version"), lock_path)
    sha256 = data.get("sha256")
    if not isinstance(sha256, str) or not SHA256_RE.match(sha256):
        raise FetchError(
            f"{lock_path}: 'sha256' is not a SHA-256 hex digest. "
            f"Pin a published release first: fetch_web_ui.py --pin {version}"
        )
    return WebUiLock(repository=repository, version=version, sha256=sha256)


def write_lock(lock_path: Path, lock: WebUiLock) -> None:
    data = {"repository": lock.repository, "version": lock.version, "sha256": lock.sha256}
    lock_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def download(url: str, target: Path) -> None:
    """Stream `url` into `target` (GitHub release links redirect; urllib follows)."""
    if not url.startswith("https://"):
        raise FetchError(f"Refusing a non-HTTPS download: {url}")
    try:
        with (
            urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as response,
            target.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)
    except OSError as exc:  # URLError and HTTPError are OSError subclasses
        raise FetchError(f"Download failed: {url}: {exc}") from None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_index(folder: Path, origin: str) -> None:
    if not (folder / "index.html").is_file():
        raise FetchError(f"{origin} has no index.html: is it a built web UI (Next.js static export)?")


def _replace_dest(staged: Path, dest: Path) -> None:
    """Swap `staged` in as `dest`; the previous `dest` survives every earlier failure."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(staged), str(dest))


def install_from_tarball(tarball: Path, expected_sha256: str, dest: Path) -> None:
    actual = sha256_of(tarball)
    if actual != expected_sha256:
        raise FetchError(
            f"SHA-256 mismatch for {tarball.name}: expected {expected_sha256}, got {actual}. "
            "Nothing was installed."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".web-dist-") as tmp:
        staged = Path(tmp) / "web"
        try:
            with tarfile.open(tarball, "r:gz") as archive:
                # "data" refuses absolute paths, `..`, links leaving the folder and device files.
                archive.extractall(staged, filter="data")
        except (tarfile.TarError, OSError) as exc:
            raise FetchError(f"Cannot unpack {tarball.name}: {exc}") from None
        _require_index(staged, tarball.name)
        _replace_dest(staged, dest)


def install_from_dir(source: Path, dest: Path) -> None:
    source = source.resolve()
    if not source.is_dir():
        raise FetchError(f"Not a folder: {source}")
    _require_index(source, str(source))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".web-dist-") as tmp:
        staged = Path(tmp) / "web"
        shutil.copytree(source, staged)
        _replace_dest(staged, dest)


def fetch(lock_path: Path, dest: Path) -> WebUiLock:
    lock = read_lock(lock_path)
    name = tarball_name(lock.version)
    with tempfile.TemporaryDirectory() as tmp:
        tarball = Path(tmp) / name
        download(release_url(lock.repository, lock.version, name), tarball)
        install_from_tarball(tarball, lock.sha256, dest)
    return lock


def parse_sha256_file(text: str, expected_name: str) -> str:
    """Read `sha256sum` output: `<hex>  <name>` (or a bare hex digest)."""
    fields = text.split()
    if not fields or not SHA256_RE.match(fields[0].lower()):
        raise FetchError(f"Not a SHA-256 checksum file for {expected_name}: {text[:80]!r}")
    if len(fields) > 1 and fields[1].lstrip("*") != expected_name:
        raise FetchError(f"The checksum file names {fields[1]!r}, expected {expected_name!r}")
    return fields[0].lower()


def pin(lock_path: Path, version: str, repository: str | None = None) -> WebUiLock:
    """Write `version` and its published SHA-256 into the lock file."""
    current: dict[str, object] = {}
    if lock_path.exists():
        try:
            current = json.loads(lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FetchError(f"{lock_path} is not valid JSON: {exc}") from None
    repository, version = _validated(repository or current.get("repository"), version, lock_path)
    name = tarball_name(version)
    with tempfile.TemporaryDirectory() as tmp:
        checksum = Path(tmp) / f"{name}.sha256"
        download(release_url(repository, version, f"{name}.sha256"), checksum)
        sha256 = parse_sha256_file(checksum.read_text(encoding="utf-8"), name)
    lock = WebUiLock(repository=repository, version=version, sha256=sha256)
    write_lock(lock_path, lock)
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_web_ui.py", description="Put the built IndieK web UI into web-dist/."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--from-dir", type=Path, help="copy a local build (e.g. ../webUI/custom-graph-explorer/out)"
    )
    mode.add_argument("--pin", metavar="VERSION", help="pin a published release in the lock file")
    parser.add_argument("--repository", help="with --pin: GitHub 'owner/name' of the web UI repo")
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="default: %(default)s")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="default: %(default)s")
    args = parser.parse_args(argv)
    if args.repository and not args.pin:
        parser.error("--repository only goes with --pin")
    try:
        if args.pin:
            lock = pin(args.lock, args.pin, args.repository)
            print(f"Pinned {lock.repository} {lock.version} (sha256 {lock.sha256}) in {args.lock}")
        elif args.from_dir:
            install_from_dir(args.from_dir, args.dest)
            print(f"Copied {args.from_dir} into {args.dest} (local build, not checked against the lock)")
        else:
            lock = fetch(args.lock, args.dest)
            print(f"Installed web UI {lock.version} ({lock.repository}, sha256 verified) into {args.dest}")
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
