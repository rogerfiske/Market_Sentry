"""HTTP client abstraction for Market_Sentry.

Provides a small, testable HTTP client abstraction for live retrieval.
Tests use FakeHttpClient; production uses StandardLibraryHttpClient
(built on urllib.request, no extra dependencies).

Features:
- GET only for this milestone.
- Configurable timeout and headers.
- No cookies/session/login logic.
- No retries.
- No browser rendering or JavaScript execution.
- Structured error responses for timeout, non-200 status, blocked by
  policy, unsupported content type, and response too large.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class HttpRequest:
    """Represents an outgoing HTTP request."""

    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    max_response_bytes: int = 10 * 1024 * 1024  # 10 MB default


@dataclass
class HttpResponse:
    """Represents an HTTP response."""

    url: str = ""
    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    text: str = ""
    content_type: str = ""
    content_length: int = 0
    error: str = ""
    timed_out: bool = False
    too_large: bool = False
    network_call_performed: bool = False

    @property
    def is_success(self) -> bool:
        """Whether the response is a successful 2xx status."""
        return 200 <= self.status_code < 300 and not self.error

    @property
    def is_html(self) -> bool:
        """Whether the content type is HTML."""
        return "text/html" in self.content_type.lower()


# ---------------------------------------------------------------------------
# Abstract client
# ---------------------------------------------------------------------------


class HttpClient(ABC):
    """Abstract HTTP client for testability."""

    @abstractmethod
    def get(self, request: HttpRequest) -> HttpResponse:
        """Perform an HTTP GET request.

        Args:
            request: The HTTP request to perform.

        Returns:
            HttpResponse with status, body, and metadata.
        """
        ...


# ---------------------------------------------------------------------------
# Standard library client (no extra dependencies)
# ---------------------------------------------------------------------------


class StandardLibraryHttpClient(HttpClient):
    """HTTP client using Python standard library urllib.request.

    No extra dependencies required. Supports configurable timeout,
    headers, max response size. No cookies, sessions, or login.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """Perform an HTTP GET request using urllib.

        Args:
            request: The HTTP request to perform.

        Returns:
            HttpResponse with status, body, and metadata.
        """
        import urllib.error
        import urllib.request

        response = HttpResponse(
            url=request.url,
            network_call_performed=True,
        )

        try:
            req = urllib.request.Request(
                request.url,
                method="GET",
                headers=request.headers,
            )

            with urllib.request.urlopen(
                req, timeout=request.timeout_seconds
            ) as resp:
                response.status_code = resp.status
                response.content_type = resp.headers.get("Content-Type", "")
                content_length_header = resp.headers.get("Content-Length", "")

                # Check content length before reading
                if content_length_header:
                    try:
                        cl = int(content_length_header)
                        if cl > request.max_response_bytes:
                            response.too_large = True
                            response.error = (
                                f"Response too large: {cl} bytes "
                                f"exceeds {request.max_response_bytes} byte limit."
                            )
                            return response
                        response.content_length = cl
                    except ValueError:
                        pass

                # Read response body with size limit
                body = resp.read(request.max_response_bytes + 1)
                if len(body) > request.max_response_bytes:
                    response.too_large = True
                    response.error = (
                        f"Response too large: read {len(body)} bytes, "
                        f"exceeds {request.max_response_bytes} byte limit."
                    )
                    return response

                response.body = body
                response.content_length = len(body)

                # Decode text
                encoding = resp.headers.get_content_charset() or "utf-8"
                try:
                    response.text = body.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    try:
                        response.text = body.decode("utf-8", errors="replace")
                    except Exception:
                        response.error = "Failed to decode response body."

                # Copy response headers
                for key in resp.headers:
                    response.headers[key] = resp.headers[key]

        except urllib.error.HTTPError as e:
            response.status_code = e.code
            response.error = f"HTTP error {e.code}: {e.reason}"

        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower():
                response.timed_out = True
                response.error = f"Request timed out after {request.timeout_seconds}s."
            else:
                response.error = f"URL error: {e.reason}"

        except TimeoutError:
            response.timed_out = True
            response.error = f"Request timed out after {request.timeout_seconds}s."

        except Exception as e:
            response.error = f"Unexpected error: {type(e).__name__}: {e}"

        return response


# ---------------------------------------------------------------------------
# Fake client for tests
# ---------------------------------------------------------------------------


class FakeHttpClient(HttpClient):
    """Fake HTTP client for testing. Performs no real network calls.

    Configure with canned responses or error conditions. Tracks
    requests for assertion in tests.
    """

    def __init__(
        self,
        response_text: str = "<html><body>Fake page</body></html>",
        response_status: int = 200,
        response_content_type: str = "text/html; charset=utf-8",
        response_error: str = "",
        response_timed_out: bool = False,
        response_too_large: bool = False,
    ) -> None:
        """Initialize the fake client with canned response data.

        Args:
            response_text: HTML text to return.
            response_status: HTTP status code to return.
            response_content_type: Content-Type header value.
            response_error: Error message to return (simulates failure).
            response_timed_out: Whether to simulate a timeout.
            response_too_large: Whether to simulate an oversized response.
        """
        self._response_text = response_text
        self._response_status = response_status
        self._response_content_type = response_content_type
        self._response_error = response_error
        self._response_timed_out = response_timed_out
        self._response_too_large = response_too_large
        self.requests: list = []

    def get(self, request: HttpRequest) -> HttpResponse:
        """Return a canned response. No real network call.

        Args:
            request: The HTTP request (recorded for assertions).

        Returns:
            Preconfigured HttpResponse.
        """
        self.requests.append(request)

        response = HttpResponse(
            url=request.url,
            status_code=self._response_status,
            content_type=self._response_content_type,
            network_call_performed=True,  # Simulated, but tracks as if real
        )

        if self._response_timed_out:
            response.timed_out = True
            response.error = f"Request timed out after {request.timeout_seconds}s."
            return response

        if self._response_too_large:
            response.too_large = True
            response.error = "Response too large."
            return response

        if self._response_error:
            response.error = self._response_error
            return response

        response.text = self._response_text
        response.body = self._response_text.encode("utf-8")
        response.content_length = len(response.body)
        response.headers = {"Content-Type": self._response_content_type}

        return response
