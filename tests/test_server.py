import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


class FakeSocket:
    def __init__(self, error=None):
        self.error = error
        self.messages = []

    def send(self, message):
        if self.error is not None:
            raise self.error
        self.messages.append(json.loads(message))


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        server.app.config.update(TESTING=True)
        self.client = server.app.test_client()
        with server.listeners_lock:
            server.listeners.clear()

    def tearDown(self):
        with server.listeners_lock:
            server.listeners.clear()

    def test_api_info(self):
        response = self.client.get("/api")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["post"], "/api/post")
        self.assertEqual(
            response.get_json()["socket"],
            "/api/socket?channel=<channel>",
        )

    def test_get_post_returns_json_usage_guidance(self):
        response = self.client.get("/api/post")
        payload = response.get_json()

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(payload["error"], "Method not allowed")
        self.assertEqual(payload["received_method"], "GET")
        self.assertEqual(payload["required"]["method"], "POST")
        self.assertEqual(set(payload["accepted_fields"]), {"url", "channel"})
        self.assertIn("POST", response.headers["Allow"])

    def test_plain_get_socket_returns_websocket_guidance(self):
        response = self.client.get("/api/socket?channel=desk")
        payload = response.get_json()

        self.assertEqual(response.status_code, 426)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(payload["error"], "WebSocket upgrade required")
        self.assertEqual(payload["required"]["method"], "GET")
        self.assertEqual(payload["required"]["protocol"], "WebSocket")
        self.assertEqual(set(payload["accepted_fields"]), {"channel"})
        self.assertEqual(response.headers["Upgrade"], "websocket")

    def test_wrong_socket_method_returns_json_usage_guidance(self):
        response = self.client.post("/api/socket")
        payload = response.get_json()

        self.assertEqual(response.status_code, 405)
        self.assertEqual(payload["error"], "Method not allowed")
        self.assertEqual(payload["required"]["method"], "GET")
        self.assertEqual(payload["required"]["protocol"], "WebSocket")

    def test_non_api_error_is_unchanged(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.is_json)

    def test_post_requires_a_url(self):
        response = self.client.post("/api/post", json={"channel": "desk"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Missing url")

    def test_post_rejects_non_http_urls(self):
        response = self.client.post(
            "/api/post",
            json={"url": "file:///tmp/example", "channel": "desk"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("http:// or https://", response.get_json()["error"])

    def test_post_only_delivers_to_the_matching_channel(self):
        matching_socket = FakeSocket()
        other_socket = FakeSocket()
        with server.listeners_lock:
            server.listeners["desk"].add(matching_socket)
            server.listeners["phone"].add(other_socket)

        response = self.client.post(
            "/api/post",
            json={"url": "https://example.com/page", "channel": "desk"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["delivered"], 1)
        self.assertEqual(
            matching_socket.messages,
            [{"url": "https://example.com/page", "channel": "desk"}],
        )
        self.assertEqual(other_socket.messages, [])

    def test_post_accepts_form_query_and_header_inputs(self):
        cases = (
            ({"data": {"url": "https://example.com/form", "channel": "form"}}, "form"),
            ({"query_string": {"url": "https://example.com/query", "channel": "query"}}, "query"),
            ({"headers": {"X-URL": "https://example.com/header", "X-Channel": "header"}}, "header"),
        )

        for request_kwargs, expected_channel in cases:
            with self.subTest(channel=expected_channel):
                response = self.client.post("/api/post", **request_kwargs)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["channel"], expected_channel)

    def test_post_defaults_to_the_none_channel(self):
        response = self.client.post(
            "/api/post",
            json={"url": "https://example.com/default"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["channel"], "none")

    def test_failed_socket_is_removed(self):
        dead_socket = FakeSocket(RuntimeError("connection closed"))
        with server.listeners_lock:
            server.listeners["desk"].add(dead_socket)

        response = self.client.post(
            "/api/post",
            json={"url": "https://example.com", "channel": "desk"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["delivered"], 0)
        with server.listeners_lock:
            self.assertNotIn("desk", server.listeners)


if __name__ == "__main__":
    unittest.main(verbosity=2)
