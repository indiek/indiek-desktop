//! IndieK Desktop shell (DESKTOP:PACKAGING-TAURI).
//!
//! Starts the local API sidecar (`indiek_api`) with `--handshake --exit-on-stdin-eof`, reads
//! its one-line JSON handshake and opens `launch_url` in the main window. The UI is served by
//! the sidecar on 127.0.0.1 and the page gets no Tauri IPC (owner decision S1 = A,
//! 2026-10-30, project_management/Design.md "Desktop seams").
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader, ErrorKind};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Deserialize;
use tauri::{AppHandle, Manager, RunEvent, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

/// Development only: path to a `fastAPI/` checkout, run with `uv` instead of the bundled sidecar.
const DEV_BACKEND_ENV: &str = "INDIEK_DESKTOP_DEV_BACKEND";
/// The built web UI the sidecar serves on `/`.
const STATIC_DIR_ENV: &str = "INDIEK_API_STATIC_DIR";
const SIDECAR_NAME: &str = if cfg!(windows) {
    "indiek-sidecar.exe"
} else {
    "indiek-sidecar"
};
const SHUTDOWN_GRACE: Duration = Duration::from_secs(5);

/// The line printed by `python -m indiek_api --handshake`.
#[derive(Deserialize)]
struct Handshake {
    indiek_api: String,
    port: u16,
    launch_url: String,
}

/// The running sidecar; its stdin is closed at exit, which stops it.
struct Sidecar(Mutex<Option<Child>>);

fn sidecar_command(app: &AppHandle) -> Result<Command, String> {
    if let Ok(dir) = std::env::var(DEV_BACKEND_ENV) {
        let mut cmd = Command::new("uv");
        cmd.args(["run", "--directory", &dir, "python", "-m", "indiek_api"]);
        return Ok(cmd);
    }
    // Both are app resources (bundle.resources in tauri.conf.json): the PyInstaller folder build
    // `indiek-sidecar/` and the built web UI `web/`.
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let mut cmd = Command::new(resources.join("indiek-sidecar").join(SIDECAR_NAME));
    cmd.arg("serve");
    // The bundled web UI, unless the environment already points elsewhere.
    let web = resources.join("web");
    if std::env::var_os(STATIC_DIR_ENV).is_none() && web.is_dir() {
        cmd.env(STATIC_DIR_ENV, web);
    }
    Ok(cmd)
}

/// The UI folder the sidecar will serve: set on the command, else inherited.
fn static_dir(cmd: &Command) -> Option<PathBuf> {
    cmd.get_envs()
        .find(|(key, _)| *key == STATIC_DIR_ENV)
        .and_then(|(_, value)| value.map(PathBuf::from))
        .or_else(|| std::env::var_os(STATIC_DIR_ENV).map(PathBuf::from))
}

fn spawn_error(program: &str, error: &std::io::Error, dev_backend_set: bool) -> String {
    let mut message = format!("The IndieK server could not be started ({program}): {error}");
    if cfg!(debug_assertions) && error.kind() == ErrorKind::NotFound && !dev_backend_set {
        message.push_str(&format!(
            ". In development, set {DEV_BACKEND_ENV} to your fastAPI folder."
        ));
    }
    message
}

/// Start the sidecar and return its handshake.
fn start_sidecar(app: &AppHandle) -> Result<Handshake, String> {
    let mut cmd = sidecar_command(app)?;
    cmd.args(["--handshake", "--exit-on-stdin-eof"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    match static_dir(&cmd) {
        Some(dir) => eprintln!("IndieK UI folder: {}", dir.display()),
        None => eprintln!("IndieK UI folder: none ({STATIC_DIR_ENV} is not set; / will be 404)"),
    }
    let program = cmd.get_program().to_string_lossy().into_owned();
    let mut child = cmd
        .spawn()
        .map_err(|e| spawn_error(&program, &e, std::env::var_os(DEV_BACKEND_ENV).is_some()))?;
    let stdout = child
        .stdout
        .take()
        .ok_or("The IndieK server has no output pipe.")?;
    app.state::<Sidecar>().0.lock().unwrap().replace(child);

    let mut reader = BufReader::new(stdout);
    let mut line = String::new();
    reader.read_line(&mut line).map_err(|e| e.to_string())?;
    // Keep draining stdout so the sidecar never blocks on a full pipe.
    std::thread::spawn(move || {
        let _ = std::io::copy(&mut reader, &mut std::io::sink());
    });
    serde_json::from_str(line.trim())
        .map_err(|_| "The IndieK server stopped before it was ready (see its log).".to_string())
}

/// Only a loopback URL on the handshake's port is ever opened.
fn launch_url(handshake: &Handshake) -> Result<Url, String> {
    let url = Url::parse(&handshake.launch_url).map_err(|e| e.to_string())?;
    let expected = url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.port() == Some(handshake.port);
    if expected {
        Ok(url)
    } else {
        Err("The IndieK server sent an unexpected address.".to_string())
    }
}

fn show_error(window: &WebviewWindow, message: &str) {
    let text = serde_json::to_string(message).unwrap_or_default();
    let _ = window.eval(format!(
        "document.getElementById('status').textContent = {text};"
    ));
}

fn open_ui(app: AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    match start_sidecar(&app).and_then(|handshake| {
        eprintln!(
            "IndieK API {} on port {}",
            handshake.indiek_api, handshake.port
        );
        launch_url(&handshake)
    }) {
        Ok(url) => {
            if let Err(e) = window.navigate(url) {
                show_error(&window, &e.to_string());
            }
        }
        Err(message) => show_error(&window, &message),
    }
}

/// Close the sidecar's stdin (it then exits by itself); kill it if it is still running later.
fn stop_sidecar(app: &AppHandle) {
    let Some(mut child) = app.state::<Sidecar>().0.lock().unwrap().take() else {
        return;
    };
    drop(child.stdin.take());
    let deadline = Instant::now() + SHUTDOWN_GRACE;
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
    let _ = child.wait();
}

/// The window may show only the bundled splash page and the local server.
fn allowed_navigation(url: &Url) -> bool {
    match url.scheme() {
        "tauri" => true,
        "http" | "https" => matches!(url.host_str(), Some("127.0.0.1") | Some("tauri.localhost")),
        _ => false,
    }
}

fn main() {
    tauri::Builder::default()
        .manage(Sidecar(Mutex::new(None)))
        .setup(|app| {
            WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("IndieK")
                .inner_size(1400.0, 900.0)
                .min_inner_size(800.0, 600.0)
                .on_navigation(allowed_navigation)
                .build()?;
            let handle = app.handle().clone();
            std::thread::spawn(move || open_ui(handle));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the IndieK app")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_sidecar(app);
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn handshake(port: u16, launch_url: &str) -> Handshake {
        Handshake {
            indiek_api: "0.16.0".into(),
            port,
            launch_url: launch_url.into(),
        }
    }

    #[test]
    fn parses_the_sidecar_handshake_line() {
        let line = r#"{"indiek_api": "0.16.0", "port": 51234, "launch_url": "http://127.0.0.1:51234/api/session?token=t"}"#;
        let parsed: Handshake = serde_json::from_str(line).unwrap();
        assert_eq!((parsed.indiek_api.as_str(), parsed.port), ("0.16.0", 51234));
        assert!(launch_url(&parsed).is_ok());
    }

    #[test]
    fn launch_url_must_be_loopback_http_on_the_handshake_port() {
        let ok = handshake(51234, "http://127.0.0.1:51234/api/session?token=t");
        assert!(launch_url(&ok).is_ok());
        for bad in [
            "http://127.0.0.1:9999/api/session?token=t",
            "https://127.0.0.1:51234/api/session?token=t",
            "http://localhost:51234/api/session?token=t",
            "http://example.org:51234/api/session?token=t",
            "file:///etc/passwd",
            "not a url",
        ] {
            assert!(
                launch_url(&handshake(51234, bad)).is_err(),
                "{bad} accepted"
            );
        }
    }

    #[test]
    fn spawn_errors_name_the_program_and_hint_at_the_dev_backend() {
        let missing = std::io::Error::from(ErrorKind::NotFound);
        let message = spawn_error("/app/indiek-sidecar", &missing, false);
        assert!(message.contains("(/app/indiek-sidecar)"), "{message}");
        assert!(message.contains(DEV_BACKEND_ENV), "{message}");
        assert!(!spawn_error("uv", &missing, true).contains(DEV_BACKEND_ENV));
    }

    #[test]
    fn the_ui_folder_set_on_the_command_wins() {
        let mut cmd = Command::new("x");
        cmd.env(STATIC_DIR_ENV, "/bundle/web");
        assert_eq!(static_dir(&cmd), Some(PathBuf::from("/bundle/web")));
    }

    #[test]
    fn navigation_stays_on_the_splash_page_and_the_local_server() {
        for ok in [
            "tauri://localhost/index.html",
            "http://127.0.0.1:51234/",
            "http://tauri.localhost/",
        ] {
            assert!(allowed_navigation(&Url::parse(ok).unwrap()), "{ok} refused");
        }
        for bad in [
            "https://example.org/",
            "http://localhost:51234/",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ] {
            assert!(
                !allowed_navigation(&Url::parse(bad).unwrap()),
                "{bad} allowed"
            );
        }
    }
}
