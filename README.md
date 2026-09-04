# URL Channel Relay

Tiny channel-based URL relay.

## API

### POST `/api/post`

Accepted input formats:

```json
{
  "url": "https://example.com",
  "channel": "desktop"
}
```

`channel` defaults to `none`.

The server also accepts:

- Form fields: `url`, `channel`
- Query parameters: `url`, `channel`
- Headers: `X-URL`, `X-Channel`

Only `http://` and `https://` URLs are accepted.

An unsupported method returns JSON with HTTP status `405`, the required method,
accepted input formats, and accepted fields. For example, `GET /api/post`
explains that the endpoint requires `POST` and accepts `url` and `channel`.

### WebSocket `/api/socket?channel=desktop`

Each connected receiver listens to one channel.

An ordinary HTTP request to this endpoint returns JSON with HTTP status `426`
and explains that a WebSocket connection is required. Other unsupported methods
return the same usage details with HTTP status `405`.

When a URL is posted, every receiver currently connected to that exact channel gets:

```json
{
  "url": "https://example.com",
  "channel": "desktop"
}
```

## Server

```powershell
py -m pip install -r requirements-server.txt
py server.py
```

Default Flask address:

```text
http://127.0.0.1:5000
```

Example:

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/post `
  -H "Content-Type: application/json" `
  -d '{"url":"https://example.com","channel":"desktop"}'
```

Or with headers:

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/post `
  -H "X-URL: https://example.com" `
  -H "X-Channel: desktop"
```

## Receiver

Edit `config.json`:

```json
{
  "server_url": "http://127.0.0.1:5000",
  "channel": "desktop",
  "receive_url_behavior": "prompt"
}
```

`receive_url_behavior`:

- `open`: immediately open received URLs in the default browser
- `prompt`: show a Yes/No confirmation first

Run as Python:

```powershell
py -m pip install -r requirements-receiver.txt
py receiver.py
```

The tray menu has:

- Open config
- Reload config
- Quit

## Nuitka standalone-folder build

```powershell
.\build_receiver.ps1
```

Output is a normal Nuitka standalone folder, not one-file mode.

The build includes Windows executable metadata and an application icon. Those help the binary look like a normal packaged application, but no metadata can guarantee that antivirus software will never produce a false positive. Code-signing the final executable with a trusted certificate is the strongest extra step if you distribute it widely.

## Tests

Install the small test dependency set:

```powershell
py -m pip install -r requirements-test.txt
```

Run the server API tests:

```powershell
py tests/test_server.py
```

Run the receiver routing test:

```powershell
py tests/test_receiver.py
```

The receiver test starts a local server on an available port, listens on a unique
channel, and publishes once to a different channel and once to the listening
channel. It asserts that only the same-channel URL is received.

## Security

There is intentionally no authentication in this minimal version. Anyone who can reach `/api/post` can send a URL to connected receivers.

For anything exposed outside a trusted LAN, put it behind authentication or add an API key.
