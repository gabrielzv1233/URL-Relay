from flask import Flask, jsonify, request
from collections import defaultdict
from urllib.parse import urlparse
from flask_sock import Sock
from threading import Lock
import json


app = Flask(__name__)
sock = Sock(app)

listeners = defaultdict(set)
listeners_lock = Lock()


def normalize_channel(value):
    value = str(value or "none").strip()
    return value or "none"


def valid_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


@app.get("/api")
def api_info():
    return jsonify({
        "service": "URL Channel Relay",
        "post": "/api/post",
        "socket": "/api/socket?channel=<channel>",
    })


@app.post("/api/post")
def post_url():
    data = request.get_json(silent=True) or {}

    url = (
        data.get("url")
        or request.form.get("url")
        or request.args.get("url")
        or request.headers.get("X-URL")
    )
    channel = normalize_channel(
        data.get("channel")
        or request.form.get("channel")
        or request.args.get("channel")
        or request.headers.get("X-Channel")
    )

    if not url:
        return jsonify({"ok": False, "error": "Missing url"}), 400

    url = str(url).strip()
    if not valid_url(url):
        return jsonify({
            "ok": False,
            "error": "URL must use http:// or https://",
        }), 400

    payload = json.dumps({"url": url, "channel": channel})
    delivered = 0
    dead = []

    with listeners_lock:
        targets = tuple(listeners.get(channel, ()))

    for ws in targets:
        try:
            ws.send(payload)
            delivered += 1
        except Exception:
            dead.append(ws)

    if dead:
        with listeners_lock:
            for ws in dead:
                listeners[channel].discard(ws)
            if not listeners[channel]:
                listeners.pop(channel, None)

    return jsonify({
        "ok": True,
        "url": url,
        "channel": channel,
        "delivered": delivered,
    })


@sock.route("/api/socket")
def socket(ws):
    channel = normalize_channel(request.args.get("channel"))

    with listeners_lock:
        listeners[channel].add(ws)

    try:
        while True:
            message = ws.receive()
            if message is None:
                break
    finally:
        with listeners_lock:
            listeners[channel].discard(ws)
            if not listeners[channel]:
                listeners.pop(channel, None)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
