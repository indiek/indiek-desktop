"""DESKTOP:PACKAGING-TAURI P6: `scripts/fetch_web_ui.py` puts a verified web UI into web-dist/."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

import fetch_web_ui as fw

REPO = "indiek/indiek-webui"
VERSION = "0.5.0"


def make_tarball(path: Path, files: dict[str, bytes], *, extra: tarfile.TarInfo | None = None) -> str:
    """Write a .tar.gz like the web UI release (members relative to out/); return its SHA-256."""
    with tarfile.open(path, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        if extra is not None:
            archive.addfile(extra, io.BytesIO(b""))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_lock(path: Path, **overrides: str) -> Path:
    data = {"repository": REPO, "version": VERSION, "sha256": "0" * 64} | overrides
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class FakeRelease(dict[str, bytes]):
    """Release files keyed by URL, served instead of the network; records each request."""

    def __init__(self) -> None:
        super().__init__()
        self.requested: list[str] = []

    def download(self, url: str, target: Path) -> None:
        self.requested.append(url)
        if url not in self:
            raise fw.FetchError(f"Download failed: {url}: HTTP Error 404: Not Found")
        target.write_bytes(self[url])


@pytest.fixture
def fake_release(monkeypatch: pytest.MonkeyPatch) -> FakeRelease:
    release = FakeRelease()
    monkeypatch.setattr(fw, "download", release.download)
    return release

UI = {"index.html": b"<html>graph</html>", "_next/static/app.js": b"console.log(1)"}


def tarball_url(version: str = VERSION) -> str:
    return fw.release_url(REPO, version, fw.tarball_name(version))


# --- names and URLs -------------------------------------------------------------------------


def test_release_url_matches_the_web_ui_release_workflow() -> None:
    assert fw.tarball_name("0.5.0") == "custom-graph-explorer-0.5.0-out.tar.gz"
    assert tarball_url() == (
        "https://github.com/indiek/indiek-webui/releases/download/0.5.0/"
        "custom-graph-explorer-0.5.0-out.tar.gz"
    )


def test_download_refuses_plain_http(tmp_path: Path) -> None:
    with pytest.raises(fw.FetchError, match="non-HTTPS"):
        fw.download("http://example.org/x.tar.gz", tmp_path / "x")


# --- lock file ------------------------------------------------------------------------------


def test_the_committed_lock_file_names_a_repository_and_version() -> None:
    data = json.loads(fw.DEFAULT_LOCK.read_text(encoding="utf-8"))
    assert fw.REPOSITORY_RE.match(data["repository"])
    assert fw.VERSION_RE.match(data["version"])


def test_an_unpinned_lock_says_how_to_pin(tmp_path: Path) -> None:
    lock = write_lock(tmp_path / "lock.json", sha256="TO-BE-PINNED")
    with pytest.raises(fw.FetchError, match=r"--pin 0\.5\.0"):
        fw.read_lock(lock)


@pytest.mark.parametrize(
    ("field", "value"),
    [("repository", "not a repo"), ("repository", "a/b/c"), ("version", "v0.5.0"), ("version", "0.5")],
)
def test_malformed_lock_fields_are_refused(tmp_path: Path, field: str, value: str) -> None:
    lock = write_lock(tmp_path / "lock.json", **{field: value})
    with pytest.raises(fw.FetchError, match=field):
        fw.read_lock(lock)


def test_missing_or_invalid_lock_files(tmp_path: Path) -> None:
    with pytest.raises(fw.FetchError, match="not found"):
        fw.read_lock(tmp_path / "absent.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(fw.FetchError, match="not valid JSON"):
        fw.read_lock(bad)


# --- fetch (download + verify + unpack) -----------------------------------------------------


def test_fetch_verifies_and_unpacks_into_dest(tmp_path: Path, fake_release: FakeRelease) -> None:
    sha = make_tarball(tmp_path / "ui.tar.gz", UI)
    fake_release[tarball_url()] = (tmp_path / "ui.tar.gz").read_bytes()
    lock = write_lock(tmp_path / "lock.json", sha256=sha)
    dest = tmp_path / "web-dist"

    assert fw.fetch(lock, dest).version == VERSION
    assert (dest / "index.html").read_bytes() == UI["index.html"]
    assert (dest / "_next/static/app.js").read_bytes() == UI["_next/static/app.js"]
    assert fake_release.requested == [tarball_url()]


def test_fetch_replaces_an_older_web_dist(tmp_path: Path, fake_release: FakeRelease) -> None:
    sha = make_tarball(tmp_path / "ui.tar.gz", UI)
    fake_release[tarball_url()] = (tmp_path / "ui.tar.gz").read_bytes()
    dest = tmp_path / "web-dist"
    dest.mkdir()
    (dest / "stale.js").write_text("old", encoding="utf-8")

    fw.fetch(write_lock(tmp_path / "lock.json", sha256=sha), dest)
    assert not (dest / "stale.js").exists()
    assert (dest / "index.html").is_file()


def test_a_hash_mismatch_installs_nothing(tmp_path: Path, fake_release: FakeRelease) -> None:
    make_tarball(tmp_path / "ui.tar.gz", UI)
    fake_release[tarball_url()] = (tmp_path / "ui.tar.gz").read_bytes()
    dest = tmp_path / "web-dist"
    dest.mkdir()
    (dest / "index.html").write_text("previous build", encoding="utf-8")

    with pytest.raises(fw.FetchError, match="SHA-256 mismatch"):
        fw.fetch(write_lock(tmp_path / "lock.json", sha256="f" * 64), dest)
    assert (dest / "index.html").read_text(encoding="utf-8") == "previous build"


def test_a_missing_release_is_reported(tmp_path: Path, fake_release: FakeRelease) -> None:
    with pytest.raises(fw.FetchError, match="404"):
        fw.fetch(write_lock(tmp_path / "lock.json"), tmp_path / "web-dist")


def test_path_traversal_in_the_tarball_is_refused(tmp_path: Path) -> None:
    evil = tarfile.TarInfo("../escaped.txt")
    sha = make_tarball(tmp_path / "ui.tar.gz", UI, extra=evil)
    dest = tmp_path / "out" / "web-dist"
    with pytest.raises(fw.FetchError, match="Cannot unpack"):
        fw.install_from_tarball(tmp_path / "ui.tar.gz", sha, dest)
    assert not (tmp_path / "out" / "escaped.txt").exists()
    assert not dest.exists()


def test_symlinks_leaving_the_folder_are_refused(tmp_path: Path) -> None:
    link = tarfile.TarInfo("passwd")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    sha = make_tarball(tmp_path / "ui.tar.gz", UI, extra=link)
    with pytest.raises(fw.FetchError, match="Cannot unpack"):
        fw.install_from_tarball(tmp_path / "ui.tar.gz", sha, tmp_path / "web-dist")


def test_a_tarball_without_index_html_is_refused(tmp_path: Path) -> None:
    sha = make_tarball(tmp_path / "ui.tar.gz", {"readme.txt": b"hi"})
    with pytest.raises(fw.FetchError, match="no index.html"):
        fw.install_from_tarball(tmp_path / "ui.tar.gz", sha, tmp_path / "web-dist")
    assert not (tmp_path / "web-dist").exists()


def test_a_corrupt_tarball_is_refused(tmp_path: Path) -> None:
    junk = tmp_path / "ui.tar.gz"
    junk.write_bytes(b"not a tarball")
    sha = hashlib.sha256(junk.read_bytes()).hexdigest()
    with pytest.raises(fw.FetchError, match="Cannot unpack"):
        fw.install_from_tarball(junk, sha, tmp_path / "web-dist")


# --- --from-dir -----------------------------------------------------------------------------


def test_from_dir_copies_a_local_build(tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "_next").mkdir(parents=True)
    (out / "index.html").write_text("local", encoding="utf-8")
    (out / "_next" / "a.js").write_text("js", encoding="utf-8")
    dest = tmp_path / "web-dist"
    dest.mkdir()
    (dest / "stale.js").write_text("old", encoding="utf-8")

    fw.install_from_dir(out, dest)
    assert (dest / "index.html").read_text(encoding="utf-8") == "local"
    assert (dest / "_next" / "a.js").is_file()
    assert not (dest / "stale.js").exists()
    assert (out / "index.html").is_file()  # the source is left alone


def test_from_dir_refuses_a_folder_that_is_not_a_build(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    with pytest.raises(fw.FetchError, match="no index.html"):
        fw.install_from_dir(tmp_path / "src", tmp_path / "web-dist")
    with pytest.raises(fw.FetchError, match="Not a folder"):
        fw.install_from_dir(tmp_path / "absent", tmp_path / "web-dist")


# --- --pin ----------------------------------------------------------------------------------


def test_pin_writes_the_published_checksum(tmp_path: Path, fake_release: FakeRelease) -> None:
    name = fw.tarball_name("0.6.0")
    digest = "ab" * 32
    fake_release[fw.release_url(REPO, "0.6.0", f"{name}.sha256")] = f"{digest}  {name}\n".encode()
    lock_path = write_lock(tmp_path / "lock.json", sha256="TO-BE-PINNED")

    fw.pin(lock_path, "0.6.0")
    assert json.loads(lock_path.read_text(encoding="utf-8")) == {
        "repository": REPO,
        "version": "0.6.0",
        "sha256": digest,
    }
    assert fw.read_lock(lock_path).sha256 == digest


def test_pin_can_set_the_repository(tmp_path: Path, fake_release: FakeRelease) -> None:
    name = fw.tarball_name(VERSION)
    fake_release[fw.release_url("indiek/other-ui", VERSION, f"{name}.sha256")] = ("cd" * 32).encode()
    lock_path = tmp_path / "new-lock.json"

    fw.pin(lock_path, VERSION, "indiek/other-ui")
    assert fw.read_lock(lock_path).repository == "indiek/other-ui"


@pytest.mark.parametrize(
    "content",
    ["", "not-a-hash  custom-graph-explorer-0.5.0-out.tar.gz", f"{'ab' * 32}  other-file.tar.gz"],
)
def test_pin_refuses_a_bad_checksum_file(
    tmp_path: Path, fake_release: FakeRelease, content: str
) -> None:
    name = fw.tarball_name(VERSION)
    fake_release[fw.release_url(REPO, VERSION, f"{name}.sha256")] = content.encode()
    lock_path = write_lock(tmp_path / "lock.json", sha256="TO-BE-PINNED")
    before = lock_path.read_text(encoding="utf-8")

    with pytest.raises(fw.FetchError):
        fw.pin(lock_path, VERSION)
    assert lock_path.read_text(encoding="utf-8") == before


# --- command line ---------------------------------------------------------------------------


def test_main_reports_errors_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = write_lock(tmp_path / "lock.json", sha256="TO-BE-PINNED")
    assert fw.main(["--lock", str(lock), "--dest", str(tmp_path / "web-dist")]) == 1
    assert capsys.readouterr().err.startswith("error: ")


def test_main_from_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "index.html").write_text("x", encoding="utf-8")
    assert fw.main(["--from-dir", str(out), "--dest", str(tmp_path / "web-dist")]) == 0
    assert (tmp_path / "web-dist" / "index.html").is_file()
    assert "local build" in capsys.readouterr().out


def test_main_rejects_repository_without_pin(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        fw.main(["--repository", REPO])
    assert "--repository only goes with --pin" in capsys.readouterr().err
