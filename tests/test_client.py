import asyncio
import json
import urllib.parse
from typing import Any, Dict, Optional


class Response:
    """Lightweight HTTP response representation for tests."""

    def __init__(self, status_code: int, headers: Dict[str, str], content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    def json(self) -> Any:
        """Parse response content as JSON."""
        return json.loads(self.content.decode("utf-8"))

    @property
    def text(self) -> str:
        """Return response content as a decoded UTF-8 string."""
        return self.content.decode("utf-8")


class SimpleTestClient:
    """Zero-dependency ASGI HTTP test client using Python standard library."""

    def __init__(self, app):
        self.app = app

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        return asyncio.run(self.async_request(method, url, params, json_body, headers))

    async def async_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path or "/"

        query_params = dict(urllib.parse.parse_qsl(parsed.query))
        if params:
            for k, v in params.items():
                query_params[k] = str(v)
        query_string = urllib.parse.urlencode(query_params).encode("ascii")

        raw_headers = []
        if headers:
            for k, v in headers.items():
                raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

        body_bytes = b""
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode("utf-8")
            raw_headers.append((b"content-type", b"application/json"))
            raw_headers.append((b"content-length", str(len(body_bytes)).encode("ascii")))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.1"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": urllib.parse.unquote(path),
            "raw_path": path.encode("ascii"),
            "query_string": query_string,
            "headers": raw_headers,
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
            "app": self.app,
        }

        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        response_status = 200
        response_headers = {}
        response_body = []

        async def send(message):
            nonlocal response_status, response_headers
            if message["type"] == "http.response.start":
                response_status = message["status"]
                for k, v in message.get("headers", []):
                    response_headers[k.decode("latin-1").lower()] = v.decode("latin-1")
            elif message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))

        await self.app(scope, receive, send)

        return Response(response_status, response_headers, b"".join(response_body))

    def get(self, url: str, **kwargs) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, json: Optional[Any] = None, **kwargs) -> Response:
        return self.request("POST", url, json_body=json, **kwargs)

    def patch(self, url: str, json: Optional[Any] = None, **kwargs) -> Response:
        return self.request("PATCH", url, json_body=json, **kwargs)

    def put(self, url: str, json: Optional[Any] = None, **kwargs) -> Response:
        return self.request("PUT", url, json_body=json, **kwargs)

    def delete(self, url: str, **kwargs) -> Response:
        return self.request("DELETE", url, **kwargs)
