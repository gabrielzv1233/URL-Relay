from flask import Flask, jsonify, request
from collections import defaultdict
from urllib.parse import urlparse
from flask_sock import Sock
from threading import Lock
import json
import os


app = Flask(__name__)
sock = Sock(app)

listeners = defaultdict(set)
listeners_lock = Lock()

API_GUIDANCE = {
    "/api": {
        "required": {"method": "GET"},
        "accepted_fields": {},
    },
    "/api/post": {
        "required": {"method": "POST"},
        "accepted_inputs": [
            {"content_type": "application/json", "fields": ["url", "channel"]},
            {"content_type": "application/x-www-form-urlencoded", "fields": ["url", "channel"]},
            {"location": "query", "fields": ["url", "channel"]},
            {"location": "headers", "fields": ["X-URL", "X-Channel"]},
        ],
        "accepted_fields": {
            "url": "Required. An http:// or https:// URL.",
            "channel": "Optional. Defaults to 'none'.",
        },
    },
    "/api/socket": {
        "required": {
            "method": "GET",
            "protocol": "WebSocket",
            "url": "/api/socket?channel=<channel>",
        },
        "accepted_inputs": [
            {"location": "query", "fields": ["channel"]},
        ],
        "accepted_fields": {
            "channel": "Optional. Defaults to 'none'.",
        },
    },
}


def normalize_channel(value):
    value = str(value or "none").strip()
    return value or "none"


def valid_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def api_error(message, status_code, guidance):
    response = jsonify({
        "ok": False,
        "error": message,
        "endpoint": request.path,
        "received_method": request.method,
        **guidance,
    })
    response.status_code = status_code
    response.headers["Allow"] = guidance["required"]["method"]
    return response


@app.before_request
def require_websocket_upgrade():
    if (
        request.path == "/api/socket"
        and request.method == "GET"
        and request.headers.get("Upgrade", "").lower() != "websocket"
    ):
        response = api_error(
            "WebSocket upgrade required",
            426,
            API_GUIDANCE["/api/socket"],
        )
        response.headers["Upgrade"] = "websocket"
        return response

    return None


@app.errorhandler(405)
def method_not_allowed(error):
    guidance = API_GUIDANCE.get(request.path)
    if guidance is None:
        return error

    return api_error("Method not allowed", 405, guidance)


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
    host = os.getenv("INTERNAL_IP", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 5000))
    app.run(host=host, port=port, debug=True)
