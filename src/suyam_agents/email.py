"""Email integration step handlers.

EmailSMTPHandler is registered for step type "email.smtp".
EmailM365Handler is registered for step type "email.m365".

In production workflows, email steps are executed inside an ephemeral LXC
container (email-agent) via ScriptDispatcher.dispatch() in runner.py.
This in-process handler:
  - Satisfies the pluggy registry so validate-step-types can confirm the step type is known
  - Implements the full send logic for test/mock contexts without a container

The actual production execution path is:
  runner.py execute_workflow()
    → self._dispatcher.dispatch()
    → run_container_lifecycle()
    → pct exec: python3 /opt/suyam/email_smtp.py  (or email_m365.py)

D-14: EmailM365Handler reuses the same Azure AD app registration as the Teams
trigger. The app registration must have Mail.Send application permission in
addition to ChannelMessage.Read.All.

msgraph-sdk and azure-identity are lazy-imported via try/except inside run() —
the packages are not installed until Plan 05 checkpoint. The handler import
itself must not fail before Plan 05.
"""

import asyncio
import os
import smtplib
from email.message import EmailMessage
from typing import Any

import pluggy

from suyam_agents.exceptions import FatalError, TransientError

hookimpl = pluggy.HookimplMarker("suyam")


def _create_graph_client(tenant_id: str, client_id: str, client_secret: str) -> Any:
    """Create a GraphServiceClient with ClientSecretCredential.

    Lazy-imports msgraph and azure.identity to avoid ImportError before Plan 05.
    """
    try:
        from azure.identity import ClientSecretCredential
        from msgraph import GraphServiceClient
    except ImportError as exc:
        raise FatalError(
            "email.m365: msgraph-sdk and azure-identity are not installed. "
            "Run Plan 05 package install checkpoint before using email.m365 steps."
        ) from exc

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    return GraphServiceClient(credentials=credential)


class EmailSMTPHandler:
    """Step handler for 'email.smtp' step type.

    Sends email via smtplib with port-based TLS detection:
      - port 465 → SMTP_SSL (implicit TLS)
      - any other port (typically 587) → SMTP + STARTTLS

    Error classification:
      - SMTPRecipientsRefused, SMTPDataError → FatalError (EMAIL-05: delivery failure)
      - SMTPServerDisconnected, TimeoutError → TransientError (retryable)
    """

    STEP_TYPE = "email_smtp"
    DISPLAY_NAME = "Email (SMTP)"
    DESCRIPTION = "Sends an email via SMTP"
    AGENT_TYPE = "email"
    VERSION = "1.0.0"
    PARAMS_SCHEMA = {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}

    def run(self, step: object, context: dict) -> str:
        """Execute an email.smtp step using smtplib.

        Args:
            step: Duck-typed step object with rendered config containing:
                  - to: recipient email address (required)
                  - subject: email subject (required)
                  - body: email body text (optional; falls back to step.config["input"])
                  - host: SMTP server hostname (required)
                  - port: SMTP server port, int (default 587)
                  - username: SMTP username / From address (required)
                  - password: SMTP password (required)
            context: Jinja2 execution context (not used for SMTP config).

        Returns:
            "sent" on success.

        Raises:
            FatalError: Missing required config fields; bad recipient; SMTP data error.
            TransientError: SMTP server disconnected; connection timeout.
        """
        # --- Extract and validate required fields ---
        to: str = step.config.get("to", "")  # type: ignore[attr-defined]
        if not to:
            raise FatalError("email.smtp: 'to' is required in step config")

        subject: str = step.config.get("subject", "")  # type: ignore[attr-defined]
        if not subject:
            raise FatalError("email.smtp: 'subject' is required in step config")

        body: str = step.config.get("body", step.config.get("input", ""))  # type: ignore[attr-defined]

        host: str = step.config.get("host", "")  # type: ignore[attr-defined]
        if not host:
            raise FatalError("email.smtp: 'host' is required in step config")

        port: int = int(step.config.get("port", 587))  # type: ignore[attr-defined]
        username: str = step.config.get("username", "")  # type: ignore[attr-defined]
        if not username:
            raise FatalError("email.smtp: 'username' is required in step config")

        password: str = step.config.get("password", "")  # type: ignore[attr-defined]
        if not password:
            raise FatalError("email.smtp: 'password' is required in step config")

        # --- Build EmailMessage ---
        msg = EmailMessage()
        msg["From"] = username
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        # --- Send with port-based TLS detection ---
        try:
            if port == 465:
                # Implicit TLS (SSL/TLS)
                with smtplib.SMTP_SSL(host, port) as smtp:
                    smtp.login(username, password)
                    smtp.send_message(msg)
            else:
                # Explicit TLS (STARTTLS) — port 587 or other
                with smtplib.SMTP(host, port) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()  # RFC 3207: re-identify after TLS upgrade
                    smtp.login(username, password)
                    smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as e:
            raise FatalError(
                f"email.smtp: recipients refused by server — {e}"
            ) from e
        except smtplib.SMTPDataError as e:
            raise FatalError(
                f"email.smtp: SMTP data error (message rejected) — {e}"
            ) from e
        except smtplib.SMTPServerDisconnected as e:
            raise TransientError(
                f"email.smtp: server disconnected unexpectedly — {e}"
            ) from e
        except TimeoutError as e:
            raise TransientError(
                f"email.smtp: connection timed out — {e}"
            ) from e

        return "sent"


class EmailM365Handler:
    """Step handler for 'email.m365' step type.

    Sends email via Microsoft Graph API users/{sender_user_id}/sendMail endpoint
    using the same Azure AD app registration as the Teams trigger (D-14).

    App registration requirements:
      - Mail.Send application permission (in addition to ChannelMessage.Read.All)
      - sender_user_id must be the UPN or Object ID of the sending mailbox
        The /me endpoint is unavailable in app-only (client credentials) flow.
        (RESEARCH.md Pitfall 7 — /me returns 403 in app-only context)

    Error classification:
      - Graph API 4xx response → FatalError (bad request, auth failure, not found)
      - Graph API 5xx response → TransientError (retryable server error)
    """

    STEP_TYPE = "email_m365"
    DISPLAY_NAME = "Email (M365)"
    DESCRIPTION = "Sends an email via Microsoft 365 Graph API"
    AGENT_TYPE = "email"
    VERSION = "1.0.0"
    PARAMS_SCHEMA = {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}

    def run(self, step: object, context: dict) -> str:
        """Execute an email.m365 step using Microsoft Graph API.

        email.m365 reuses Teams Azure AD credentials (D-14). The app registration
        must have Mail.Send application permission AND ChannelMessage.Read.All.
        sender_user_id must be the UPN or Object ID of the sending mailbox —
        the /me endpoint is unavailable in app-only flow (RESEARCH.md Pitfall 7).

        Args:
            step: Duck-typed step object with rendered config containing:
                  - to: recipient email address (required)
                  - subject: email subject (required)
                  - body: email body text (optional)
                  - sender_user_id: UPN or Object ID of sending mailbox (required)
            context: Jinja2 execution context (not used for M365 config).

        Azure AD credentials are read from environment variables (not step.config):
                  - SUYAM_CRED_TEAMS_TENANT_ID: Azure AD tenant ID
                  - SUYAM_CRED_TEAMS_CLIENT_ID: Azure AD app client ID
                  - SUYAM_CRED_TEAMS_CLIENT_SECRET: Azure AD app client secret

        Returns:
            "sent" on success.

        Raises:
            FatalError: Missing required config; Graph API 4xx response.
            TransientError: Graph API 5xx response.
        """
        # --- Extract and validate required fields ---
        to: str = step.config.get("to", "")  # type: ignore[attr-defined]
        if not to:
            raise FatalError("email.m365: 'to' is required in step config")

        subject: str = step.config.get("subject", "")  # type: ignore[attr-defined]
        if not subject:
            raise FatalError("email.m365: 'subject' is required in step config")

        body: str = step.config.get("body", step.config.get("input", ""))  # type: ignore[attr-defined]

        tenant_id: str = os.environ.get('SUYAM_CRED_TEAMS_TENANT_ID', '')
        if not tenant_id:
            raise FatalError(
                "email.m365: SUYAM_CRED_TEAMS_TENANT_ID env var is not set or empty."
            )

        client_id: str = os.environ.get('SUYAM_CRED_TEAMS_CLIENT_ID', '')
        if not client_id:
            raise FatalError(
                "email.m365: SUYAM_CRED_TEAMS_CLIENT_ID env var is not set or empty."
            )

        client_secret: str = os.environ.get('SUYAM_CRED_TEAMS_CLIENT_SECRET', '')
        if not client_secret:
            raise FatalError(
                "email.m365: SUYAM_CRED_TEAMS_CLIENT_SECRET env var is not set or empty."
            )

        sender_user_id: str = step.config.get("sender_user_id", "")  # type: ignore[attr-defined]
        if not sender_user_id:
            raise FatalError(
                "email.m365: 'sender_user_id' is required in step config. "
                "Must be the UPN or Object ID of the sending mailbox — "
                "/me endpoint is unavailable in app-only (client credentials) flow."
            )

        # --- Create Graph client (lazy-imports msgraph + azure.identity) ---
        graph_client = _create_graph_client(tenant_id, client_id, client_secret)

        # --- Build and send via async Graph API ---
        async def _send() -> None:
            try:
                from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
                    SendMailPostRequestBody,
                )
                from msgraph.generated.models.message import Message
                from msgraph.generated.models.item_body import ItemBody
                from msgraph.generated.models.body_type import BodyType
                from msgraph.generated.models.recipient import Recipient
                from msgraph.generated.models.email_address import EmailAddress
            except ImportError as exc:
                raise FatalError(
                    "email.m365: msgraph-sdk models not available. "
                    "Run Plan 05 package install checkpoint."
                ) from exc

            recipient = Recipient()
            email_addr = EmailAddress()
            email_addr.address = to
            recipient.email_address = email_addr

            item_body = ItemBody()
            item_body.content = body
            item_body.content_type = BodyType.Text

            message = Message()
            message.subject = subject
            message.body = item_body
            message.to_recipients = [recipient]

            request_body = SendMailPostRequestBody()
            request_body.message = message

            # sender_user_id required for app-only flow — /me endpoint unavailable
            await graph_client.users.by_user_id(sender_user_id).send_mail.post(request_body)

        try:
            # CR-03: asyncio.run() raises RuntimeError when an event loop is already
            # running (e.g. inside the trigger daemon or pytest-asyncio). Detect an
            # active loop and submit the coroutine in a thread pool instead.
            import concurrent.futures  # noqa: PLC0415
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(asyncio.run, _send()).result()
            else:
                asyncio.run(_send())
        except FatalError:
            raise
        except Exception as e:
            status_code = getattr(e, "response_status_code", None)
            if status_code is not None:
                if status_code >= 500:
                    raise TransientError(
                        f"email.m365: Graph API transient error (HTTP {status_code}): {e}"
                    ) from e
                else:
                    raise FatalError(
                        f"email.m365: Graph API error (HTTP {status_code}): {e}"
                    ) from e
            # Unknown error — treat as transient (network/DNS/timeout are retryable)
            raise TransientError(f"email.m365: unexpected error (may be retryable): {e}") from e

        return "sent"


class EmailIntegration:
    """Pluggy plugin class for the email integration.

    Provides AGENT_TYPE_MAP for AgentTypeResolver and registers step handlers
    via the @hookimpl register_handlers method (REFACTOR-02).
    """

    AGENT_TYPE_MAP: dict[str, str] = {"email": "email-agent"}
    STEP_HANDLERS: list = [EmailSMTPHandler, EmailM365Handler]

    @hookimpl
    def register_handlers(self, pm: pluggy.PluginManager) -> None:
        """Register EmailSMTPHandler and EmailM365Handler with the plugin manager."""
        pm.register(EmailSMTPHandler())
        pm.register(EmailM365Handler())


plugin = EmailIntegration()
