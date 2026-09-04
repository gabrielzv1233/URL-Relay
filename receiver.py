from urllib.parse import urlunparse, urlparse, quote
from pathlib import Path
from PIL import Image
import webbrowser
import threading
import websocket
import pystray
import ctypes
import json
import sys
import os


APP_NAME = "URL Channel Receiver"
DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:5000",
    "channel": "none",
    "receive_url_behavior": "prompt"
}


BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False) or "__compiled__" in globals()
    else Path(__file__).resolve().parent
)
CONFIG_PATH = BASE_DIR / "config.json"
ICON_PATH = BASE_DIR / "url_receiver.ico"

config_lock = threading.Lock()
config = DEFAULT_CONFIG.copy()
stop_event = threading.Event()
reconnect_event = threading.Event()


def ensure_config():
    if CONFIG_PATH.exists():
        return

    CONFIG_PATH.write_text(
        json.dumps(DEFAULT_CONFIG, indent=2),
        encoding="utf-8"
    )


def load_config():
    global config

    ensure_config()

    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to read config.json: {exc}")
        loaded = {}

    merged = DEFAULT_CONFIG | loaded
    merged["channel"] = str(merged.get("channel") or "none").strip() or "none"
    merged["receive_url_behavior"] = str(
        merged.get("receive_url_behavior") or "prompt"
    ).lower()

    if merged["receive_url_behavior"] not in {"open", "prompt"}:
        merged["receive_url_behavior"] = "prompt"

    with config_lock:
        config = merged

    return merged


def socket_url(server_url, channel):
    parsed = urlparse(server_url.strip())
    scheme = "wss" if parsed.scheme == "https" else "ws"

    base_path = parsed.path.rstrip("/")
    if base_path.endswith("/api"):
        path = f"{base_path}/socket"
    else:
        path = f"{base_path}/api/socket"

    return urlunparse((
        scheme,
        parsed.netloc,
        path,
        "",
        f"channel={quote(channel)}",
        "",
    ))


def confirm_open(url):
    if sys.platform == "win32":
        result = ctypes.windll.user32.MessageBoxW(
            None,
            f"Open this URL?\n\n{url}",
            APP_NAME,
            0x00000004 | 0x00000020 | 0x00040000,
        )
        return result == 6

    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        result = messagebox.askyesno(APP_NAME, f"Open this URL?\n\n{url}")
        root.destroy()
        return result
    except Exception:
        return False


def handle_message(message):
    try:
        payload = json.loads(message)
        url = str(payload["url"]).strip()
    except Exception:
        url = str(message).strip()

    if not url:
        return

    with config_lock:
        behavior = config["receive_url_behavior"]

    if behavior == "open" or confirm_open(url):
        webbrowser.open(url)


def socket_worker():
    while not stop_event.is_set():
        current = load_config()
        url = socket_url(current["server_url"], current["channel"])

        print(f"Connecting to {url}")

        ws = websocket.WebSocketApp(
            url,
            on_message=lambda _ws, message: handle_message(message),
            on_error=lambda _ws, error: print(f"WebSocket error: {error}"),
            on_close=lambda _ws, code, reason: print(
                f"WebSocket closed: {code} {reason or ''}".strip()
            ),
        )

        reconnect_event.clear()

        thread = threading.Thread(
            target=ws.run_forever,
            kwargs={"ping_interval": 30, "ping_timeout": 10},
            daemon=True,
        )
        thread.start()

        while thread.is_alive() and not stop_event.is_set():
            if reconnect_event.wait(0.25):
                ws.close()
                break

        ws.close()

        if not stop_event.is_set():
            stop_event.wait(2)


def open_config(_icon=None, _item=None):
    ensure_config()
    os.startfile(CONFIG_PATH) if sys.platform == "win32" else webbrowser.open(
        CONFIG_PATH.as_uri()
    )


def reload_config(_icon=None, _item=None):
    load_config()
    reconnect_event.set()


def quit_app(icon, _item=None):
    stop_event.set()
    reconnect_event.set()
    icon.stop()


if __name__ == "__main__":
    load_config()
    threading.Thread(target=socket_worker, daemon=True).start()

    tray_image = (
        Image.open(ICON_PATH)
        if ICON_PATH.exists()
        else Image.new("RGBA", (64, 64), (45, 45, 45, 255))
    )
    icon = pystray.Icon(
        "url_channel_receiver",
        tray_image,
        APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Open config", open_config),
            pystray.MenuItem("Reload config", reload_config),
            pystray.MenuItem("Quit", quit_app),
        ),
    )
    icon.run()
