"""HTTP request integration step handler.

HttpRequestHandler is registered for step type "http.request".

In production workflows, http.request steps are executed inside an ephemeral
LXC container (common-agent) via ScriptDispatcher.dispatch() in runner.py.
This in-process handler:
  - Satisfies the pluggy registry so validate-step-types can confirm the step type is known
  - Implements the full HTTP send logic for test/mock contexts without a container

The actual production execution path is:
  runner.py execute_workflow()
    → self._dispatcher.dispatch()
    → run_container_lifecycle()
    → pct exec: python3 /opt/suyam/http_request.py

HTTP-03: The response body (response.text) is returned as the step output and
stored in the steps table. It is available for subsequent steps via Jinja2
interpolation as {{ steps.<id>.output }}.

httpx is lazy-imported inside run() to prevent ImportError at module load time
if httpx is not installed (though httpx is a transitive dep of msgraph-sdk and
should be available after Plan 05).
"""

import pluggy

from suyam_agents.exceptions import FatalError, TransientError

hookimpl = pluggy.HookimplMarker("suyam")

# Lazy-import httpx at module level — httpx is used by msgraph-sdk and is
# expected to be installed, but guard against ImportError before Plan 05.
try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    _HTTPX_AVAILABLE = False


class HttpRequestHandler:
    """Step handler for 'http.request' step type.

    Sends HTTP requests (GET/POST/PUT/DELETE) using httpx.Client.
    Returns response.text as step output (available as {{ steps.<id>.output }}).

    Error classification (HTTP-01, HTTP-02):
      - HTTP 5xx status → TransientError (retryable: server error)
      - HTTP 4xx status → FatalError (non-retryable: bad request, auth failure)

    Both error messages include: f"HTTP {status_code}: {response.text[:200]}"
    """

    STEP_TYPE = "http"
    DISPLAY_NAME = "HTTP Request"
    DESCRIPTION = "Makes an HTTP request to a URL"
    AGENT_TYPE = "http"
    VERSION = "1.0.0"
    PARAMS_SCHEMA = {"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]}, "body": {"type": "object"}}, "required": ["url"]}

    def run(self, step: object, context: dict) -> str:
        """Execute an http.request step using httpx.

        Args:
            step: Duck-typed step object with rendered config containing:
                  - method: HTTP method string (default "GET")
                  - url: target URL (required)
                  - headers: dict of request headers (optional, default {})
                  - body: request body — dict (sent as JSON) or str (raw content) (optional)
                  - timeout: request timeout in seconds, int (default 30)
            context: Jinja2 execution context (not used for HTTP config).

        Returns:
            response.text — the full response body as a string. Available as
            {{ steps.<id>.output }} in subsequent step configs (HTTP-03).

        Raises:
            FatalError: Missing required 'url'; HTTP 4xx status response.
            TransientError: HTTP 5xx status response.
        """
        if not _HTTPX_AVAILABLE:
            raise FatalError(
                "http.request: httpx is not installed. "
                "Run Plan 05 package install checkpoint before using http.request steps."
            )

        # --- Extract config values ---
        method: str = step.config.get("method", "GET").upper()  # type: ignore[attr-defined]

        url: str = step.config.get("url", "")  # type: ignore[attr-defined]
        if not url:
            raise FatalError("http.request: 'url' is required in step config")

        headers: dict = step.config.get("headers", {})  # type: ignore[attr-defined]
        body = step.config.get("body", None)  # type: ignore[attr-defined]
        timeout: int = int(step.config.get("timeout", 30))  # type: ignore[attr-defined]

        # --- Build request kwargs ---
        kwargs: dict = {
            "method": method,
            "url": url,
            "headers": headers,
        }

        if body is not None:
            if isinstance(body, dict):
                kwargs["json"] = body
            else:
                kwargs["content"] = body

        # --- Send request and classify response ---
        with httpx.Client(timeout=timeout) as client:
            response = client.request(**kwargs)

        if response.status_code >= 500:
            raise TransientError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        if response.status_code >= 400:
            raise FatalError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        # HTTP-03: return response body — available as {{ steps.<id>.output }}
        return response.text


class HttpIntegration:
    """Pluggy plugin class for the HTTP integration.

    Provides AGENT_TYPE_MAP for AgentTypeResolver and registers step handlers
    via the @hookimpl register_handlers method (REFACTOR-02).
    """

    AGENT_TYPE_MAP: dict[str, str] = {"http": "common-agent"}
    STEP_HANDLERS: list = [HttpRequestHandler]

    @hookimpl
    def register_handlers(self, pm: pluggy.PluginManager) -> None:
        """Register HttpRequestHandler with the plugin manager."""
        pm.register(HttpRequestHandler())


plugin = HttpIntegration()
