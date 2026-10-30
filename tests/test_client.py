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


class AsyncStreamResponse:
    """Represents an active streaming HTTP response (e.g., SSE) from ASGI application."""

    def __init__(
        self,
        status_code: int,
        headers: Dict[str, str],
        chunks_queue: asyncio.Queue,
        disconnect_event: asyncio.Event,
        task: asyncio.Task,
    ):
        self.status_code = status_code
        self.headers = headers
        self._chunks_queue = chunks_queue
        self._disconnect_event = disconnect_event
        self._task = task
        self._buffer = ""
        self._closed = False
        self._collected_body = bytearray()

    async def read_chunk(self, timeout: float = 5.0) -> Optional[bytes]:
        """Read the next chunk of raw bytes, or return None on EOF."""
        if self._closed and self._chunks_queue.empty():
            return None
        try:
            chunk = await asyncio.wait_for(self._chunks_queue.get(), timeout=timeout)
            if chunk is None:
                return None
            self._collected_body.extend(chunk)
            return chunk
        except asyncio.TimeoutError:
            return None

    async def read_frame(self, timeout: float = 5.0) -> Optional[str]:
        """Read the next raw SSE frame (delimited by \\n\\n), or return None on EOF."""
        while "\n\n" not in self._buffer:
            chunk = await self.read_chunk(timeout=timeout)
            if chunk is None:
                if self._buffer.strip():
                    frame = self._buffer
                    self._buffer = ""
                    return frame
                return None
            self._buffer += chunk.decode("utf-8")

        frame, self._buffer = self._buffer.split("\n\n", 1)
        return frame + "\n\n"

    async def read_event(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Read and parse the next SSE event frame."""
        frame = await self.read_frame(timeout=timeout)
        if frame is None:
            return None
        return self._parse_sse_frame(frame)

    @staticmethod
    def _parse_sse_frame(frame: str) -> Dict[str, Any]:
        """Parse raw SSE frame into a dictionary containing event name, data, and raw frame."""
        event_name = None
        data_lines = []
        for line in frame.strip().split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        data_str = "\n".join(data_lines)
        parsed_data: Any = data_str
        try:
            parsed_data = json.loads(data_str)
        except Exception:
            pass
        return {"event": event_name, "data": parsed_data, "raw": frame}

    async def read_all_text(self, timeout: float = 5.0) -> str:
        """Read all remaining chunks from the stream as a string."""
        while True:
            chunk = await self.read_chunk(timeout=timeout)
            if chunk is None:
                break
        return self._collected_body.decode("utf-8")

    async def json(self, timeout: float = 5.0) -> Any:
        """Read remaining chunks and parse as JSON."""
        text = await self.read_all_text(timeout=timeout)
        return json.loads(text)

    async def close(self):
        """Close the stream and signal disconnect to the ASGI app."""
        if not self._closed:
            self._closed = True
            self._disconnect_event.set()
            if not self._task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(self._task), timeout=0.1)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    self._task.cancel()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class _StreamContextManager:
    """Helper allowing stream requests to be both awaited directly or used as async context manager."""

    def __init__(self, coro):
        self._coro = coro
        self._resp: Optional[AsyncStreamResponse] = None

    def __await__(self):
        return self._coro.__await__()

    async def __aenter__(self) -> AsyncStreamResponse:
        self._resp = await self._coro
        return await self._resp.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._resp is not None:
            await self._resp.__aexit__(exc_type, exc_val, exc_tb)


class AsyncTestClient:
    """Asynchronous ASGI HTTP test client with Server-Sent Events (SSE) streaming support."""

    def __init__(self, app):
        self.app = app

    def _build_scope_and_body(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
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
        return scope, body_bytes

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        scope, body_bytes = self._build_scope_and_body(method, url, params, json_body, headers)

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

    async def _start_stream(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncStreamResponse:
        scope, body_bytes = self._build_scope_and_body(method, url, params, json_body, headers)

        sent_request = False
        disconnect_event = asyncio.Event()

        async def receive():
            nonlocal sent_request
            if not sent_request:
                sent_request = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            await disconnect_event.wait()
            return {"type": "http.disconnect"}

        response_started = asyncio.Event()
        response_status = 200
        response_headers: Dict[str, str] = {}
        chunks_queue: asyncio.Queue = asyncio.Queue()

        async def send(message):
            nonlocal response_status, response_headers
            if message["type"] == "http.response.start":
                response_status = message["status"]
                for k, v in message.get("headers", []):
                    response_headers[k.decode("latin-1").lower()] = v.decode("latin-1")
                response_started.set()
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    await chunks_queue.put(body)
                if not message.get("more_body", False):
                    await chunks_queue.put(None)

        task = asyncio.create_task(self.app(scope, receive, send))

        start_waiter = asyncio.create_task(response_started.wait())
        done, _ = await asyncio.wait([task, start_waiter], return_when=asyncio.FIRST_COMPLETED)

        if task in done and task.exception():
            start_waiter.cancel()
            raise task.exception()

        return AsyncStreamResponse(
            status_code=response_status,
            headers=response_headers,
            chunks_queue=chunks_queue,
            disconnect_event=disconnect_event,
            task=task,
        )

    def stream(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> _StreamContextManager:
        return _StreamContextManager(
            self._start_stream(method, url, params=params, json_body=json_body, headers=headers)
        )

    async def get(self, url: str, **kwargs) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, json: Optional[Any] = None, **kwargs) -> Response:
        return await self.request("POST", url, json_body=json, **kwargs)

    async def patch(self, url: str, json: Optional[Any] = None, **kwargs) -> Response:
        return await self.request("PATCH", url, json_body=json, **kwargs)

    async def put(self, url: str, json: Optional[Any] = None, **kwargs) -> Response:
        return await self.request("PUT", url, json_body=json, **kwargs)

    async def delete(self, url: str, **kwargs) -> Response:
        return await self.request("DELETE", url, **kwargs)

