//! "Install `ik` Command…" menu item (DESKTOP:PACKAGING-TAURI P5).
//!
//! Writes `~/.local/bin/ik`, a shell launcher that runs the CLI bundled with the app
//! (`indiek-sidecar ik`). The CLI and the app are the same frozen binary, so they share the
//! author key's Keychain access (owner decision 2026-11-08: `~/.local/bin`, no admin prompt).

use std::ffi::OsStr;
use std::fs;
use std::io;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

/// Comment line that marks a launcher written by this app (safe to overwrite).
pub const MARKER: &str = "# Installed by IndieK Desktop.";

pub const NO_BUNDLED_CLI: &str =
    "This build has no bundled ik command (development mode). Install it from an app built with `npm run build`.";

/// What is already at the launcher path.
#[derive(Debug, PartialEq, Eq)]
pub enum Existing {
    Nothing,
    /// A launcher written by this app.
    Ours,
    /// Anything else, e.g. `ik` from `uv tool install indiek`.
    Foreign,
}

pub fn launcher_path(home: &Path) -> PathBuf {
    home.join(".local").join("bin").join("ik")
}

/// Single-quote for `sh`.
fn shell_quote(text: &str) -> String {
    format!("'{}'", text.replace('\'', r"'\''"))
}

pub fn launcher_script(sidecar: &Path) -> String {
    format!(
        "#!/bin/sh\n{MARKER} Runs the IndieK CLI bundled with the app.\nexec {} ik \"$@\"\n",
        shell_quote(&sidecar.to_string_lossy())
    )
}

pub fn existing(path: &Path) -> Existing {
    match fs::read(path) {
        Ok(bytes) if String::from_utf8_lossy(&bytes).contains(MARKER) => Existing::Ours,
        Ok(_) => Existing::Foreign,
        // A broken symlink is still something we did not write.
        Err(_) if path.symlink_metadata().is_ok() => Existing::Foreign,
        Err(_) => Existing::Nothing,
    }
}

/// Write the launcher (mode 755). Renaming a temporary file over `path` replaces a symlink
/// itself, never the file it points to.
pub fn install(path: &Path, sidecar: &Path) -> io::Result<()> {
    let dir = path
        .parent()
        .ok_or_else(|| io::Error::other("the launcher path has no folder"))?;
    fs::create_dir_all(dir)?;
    let tmp = dir.join(".ik.indiek-desktop.tmp");
    fs::write(&tmp, launcher_script(sidecar))?;
    fs::set_permissions(&tmp, fs::Permissions::from_mode(0o755))?;
    fs::rename(&tmp, path)
}

/// Whether `dir` is listed in a `PATH`-style value.
pub fn on_path(dir: &Path, path_var: Option<&OsStr>) -> bool {
    path_var.is_some_and(|value| std::env::split_paths(value).any(|entry| entry == dir))
}

pub fn replace_question(path: &Path) -> String {
    format!(
        "{} already exists and was not installed by IndieK Desktop (perhaps `uv tool install indiek`). Replace it with the app's ik command?",
        path.display()
    )
}

pub fn success_message(path: &Path, dir_on_path: bool) -> String {
    let mut message = format!(
        "Installed {}. Open a new terminal and run `ik --help`.",
        path.display()
    );
    if !dir_on_path {
        message.push_str(
            "\n\n~/.local/bin may not be on your PATH. If `ik` is not found, add this line to ~/.zshrc (or your shell's profile):\nexport PATH=\"$HOME/.local/bin:$PATH\"",
        );
    }
    message
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("indiek-p5-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        dir
    }

    #[test]
    fn launcher_goes_to_local_bin() {
        assert_eq!(
            launcher_path(Path::new("/Users/a")),
            PathBuf::from("/Users/a/.local/bin/ik")
        );
    }

    #[test]
    fn launcher_runs_the_bundled_cli_with_all_arguments() {
        let script = launcher_script(Path::new("/Applications/IndieK.app/x/indiek-sidecar"));
        assert!(script.starts_with("#!/bin/sh\n"));
        assert!(script.contains(MARKER));
        assert!(script.ends_with("exec '/Applications/IndieK.app/x/indiek-sidecar' ik \"$@\"\n"));
    }

    #[test]
    fn quotes_survive_in_the_sidecar_path() {
        assert_eq!(shell_quote("/a b/it's"), r"'/a b/it'\''s'");
    }

    #[test]
    fn installs_an_executable_launcher_and_recognises_it() {
        let home = scratch("install");
        let path = launcher_path(&home);
        assert_eq!(existing(&path), Existing::Nothing);
        install(&path, Path::new("/app/indiek-sidecar")).unwrap();
        let mode = fs::metadata(&path).unwrap().permissions().mode();
        assert_eq!(mode & 0o777, 0o755);
        assert_eq!(existing(&path), Existing::Ours);
        // Reinstalling (e.g. after the app moved) overwrites our own launcher.
        install(&path, Path::new("/moved/indiek-sidecar")).unwrap();
        assert!(fs::read_to_string(&path).unwrap().contains("/moved/"));
        fs::remove_dir_all(&home).unwrap();
    }

    #[test]
    fn other_files_and_broken_links_are_foreign() {
        let home = scratch("foreign");
        let path = launcher_path(&home);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, "#!/usr/bin/env python\n").unwrap();
        assert_eq!(existing(&path), Existing::Foreign);
        fs::remove_file(&path).unwrap();
        std::os::unix::fs::symlink(home.join("missing"), &path).unwrap();
        assert_eq!(existing(&path), Existing::Foreign);
        fs::remove_dir_all(&home).unwrap();
    }

    #[test]
    fn replacing_a_symlink_leaves_its_target_alone() {
        let home = scratch("symlink");
        let path = launcher_path(&home);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        let target = home.join("uv-tool-ik");
        fs::write(&target, "original").unwrap();
        std::os::unix::fs::symlink(&target, &path).unwrap();
        install(&path, Path::new("/app/indiek-sidecar")).unwrap();
        assert_eq!(fs::read_to_string(&target).unwrap(), "original");
        assert!(!fs::symlink_metadata(&path)
            .unwrap()
            .file_type()
            .is_symlink());
        fs::remove_dir_all(&home).unwrap();
    }

    #[test]
    fn path_hint_only_when_the_folder_is_missing_from_path() {
        let dir = Path::new("/Users/a/.local/bin");
        assert!(on_path(
            dir,
            Some(OsStr::new("/usr/bin:/Users/a/.local/bin"))
        ));
        assert!(!on_path(dir, Some(OsStr::new("/usr/bin:/bin"))));
        assert!(!on_path(dir, None));
        assert!(!success_message(dir, true).contains("export PATH"));
        assert!(success_message(dir, false).contains("export PATH"));
    }
}
