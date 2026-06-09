#!/usr/bin/env python3
"""Container script for http.request step.

Sends HTTP request (GET/POST/PUT/DELETE) using httpx; prints response body
to stdout on success.

Stdout contract: ONLY the response body on success — nothing else.
All debug, progress, and error messages go to sys.stderr.
Exit 0 on success, exit 1 on fatal error (4xx), exit 2 on transient error (5xx).

Executed by the orchestrator via:
  pct exec <vmid> -- python3 /opt/suyam/http_request.py

Environment variables read:
  SUYAM_STEP_CONFIG_METHOD   — HTTP method (default "GET")
  SUYAM_STEP_CONFIG_URL      — target URL (required)
  SUYAM_STEP_CONFIG_HEADERS  — request headers as JSON string (optional)
  SUYAM_STEP_CONFIG_BODY     — request body as JSON string (optional)
  SUYAM_STEP_INPUT           — prior step output; used as body if BODY not set (optional)

HTTP-03: Response body is printed to stdout so the orchestrator captures it
as the step output. Available in subsequent steps as {{ steps.<id>.output }}.

Exit codes:
  0 — success (2xx response)
  1 — fatal error (4xx response or request error)
  2 — transient error (5xx response — retryable by orchestrator)
"""

import json
import os
import sys


def main() -> None:
    # ── Read step config ─────────────────────────────────────────────────────
    method: str = os.environ.get("SUYAM_STEP_CONFIG_METHOD", "GET").strip().upper()
    url: str = os.environ.get("SUYAM_STEP_CONFIG_URL", "").strip()
    headers_str: str = os.environ.get("SUYAM_STEP_CONFIG_HEADERS", "").strip()
    body_str: str = os.environ.get("SUYAM_STEP_CONFIG_BODY", "").strip()
    step_input: str = os.environ.get("SUYAM_STEP_INPUT", "").strip()

    # ── Validate required inputs ─────────────────────────────────────────────
    if not url:
        sys.stderr.write("ERROR: SUYAM_STEP_CONFIG_URL is required but not set\n")
        sys.exit(1)

    # ── Parse headers ────────────────────────────────────────────────────────
    headers: dict = {}
    if headers_str:
        try:
            headers = json.loads(headers_str)
        except json.JSONDecodeError as e:
            sys.stderr.write(
                f"ERROR: SUYAM_STEP_CONFIG_HEADERS is not valid JSON: {e}\n"
            )
            sys.exit(1)

    # ── Parse body: BODY env var takes priority over STEP_INPUT ─────────────
    body = None
    raw_body = body_str or step_input
    if raw_body:
        try:
            body = json.loads(raw_body)  # parsed as JSON dict/list if valid
        except json.JSONDecodeError:
            body = raw_body  # fall back to raw string

    sys.stderr.write(
        f"[http_request] method={method} url={url} "
        f"headers_count={len(headers)} body_set={body is not None}\n"
    )

    # ── Send HTTP request ────────────────────────────────────────────────────
    try:
        import httpx
    except ImportError as e:
        sys.stderr.write(
            f"FATAL: httpx not installed: {e}\n"
            "Rebuild the container image: httpx is baked into the NixOS flake via configuration.nix\n"
        )
        sys.exit(1)

    try:
        kwargs: dict = {
            "method": method,
            "url": url,
            "headers": headers,
        }

        if body is not None:
            if isinstance(body, dict):
                kwargs["json"] = body
            else:
                kwargs["content"] = body if isinstance(body, bytes) else body.encode()

        with httpx.Client(timeout=30) as client:
            response = client.request(**kwargs)

    except Exception as e:
        sys.stderr.write(f"FATAL: HTTP request failed: {e}\n")
        sys.exit(1)

    # ── Classify response ────────────────────────────────────────────────────
    if response.status_code >= 500:
        sys.stderr.write(
            f"TRANSIENT: HTTP {response.status_code}: {response.text[:200]}\n"
        )
        sys.exit(2)  # exit 2 = transient (retryable by orchestrator)

    if response.status_code >= 400:
        sys.stderr.write(
            f"FATAL: HTTP {response.status_code}: {response.text[:200]}\n"
        )
        sys.exit(1)

    # HTTP-03: response body to stdout — captured as step output
    # Available as {{ steps.<id>.output }} in subsequent step configs
    print(response.text)


if __name__ == "__main__":
    main()
