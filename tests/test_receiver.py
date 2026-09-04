import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import websocket
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


class LiveServer:
    def __init__(self):
        self.httpd = make_server("127.0.0.1", 0, server.app, threaded=True)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def http_url(self):
        return f"http://127.0.0.1:{self.httpd.server_port}"

    @property
    def websocket_url(self):
        return f"ws://127.0.0.1:{self.httpd.server_port}"

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def publish(server_url, url, channel):
    body = json.dumps({"url": url, "channel": channel}).encode("utf-8")
    request = Request(
        f"{server_url}/api/post",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=2) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"POST /api/post failed: {exc.code} {detail}") from exc


class ReceiverRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.app.config.update(TESTING=True)
        cls.live_server = LiveServer()
        cls.live_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.live_server.stop()

    def setUp(self):
        with server.listeners_lock:
            server.listeners.clear()

    def tearDown(self):
        with server.listeners_lock:
            server.listeners.clear()

    def test_receiver_only_gets_posts_for_its_channel(self):
        channel = f"receiver-test-{uuid4().hex}"
        other_channel = f"other-test-{uuid4().hex}"
        socket = websocket.create_connection(
            f"{self.live_server.websocket_url}/api/socket?channel={channel}",
            timeout=2,
        )

        try:
            other_result = publish(
                self.live_server.http_url,
                "https://example.com/different-channel",
                other_channel,
            )
            self.assertEqual(other_result["delivered"], 0)

            socket.settimeout(0.5)
            with self.assertRaises(websocket.WebSocketTimeoutException):
                socket.recv()

            same_result = publish(
                self.live_server.http_url,
                "https://example.com/same-channel",
                channel,
            )
            self.assertEqual(same_result["delivered"], 1)

            socket.settimeout(2)
            received = json.loads(socket.recv())
            self.assertEqual(
                received,
                {
                    "url": "https://example.com/same-channel",
                    "channel": channel,
                },
            )
        finally:
            socket.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
