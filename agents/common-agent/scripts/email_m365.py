#!/usr/bin/env python3
"""Container script for email.m365 step.

Uses same Azure AD app registration as Teams trigger (D-14). Requires
Mail.Send application permission. sender_user_id must be the UPN or Object
ID of the sending mailbox — the /me endpoint is unavailable in app-only
(client credentials) flow. See RESEARCH.md Pitfall 7.

Stdout contract: ONLY 'sent' on success — nothing else.
All debug, progress, and error messages go to sys.stderr.
Exit 0 on success, non-zero on failure.

Executed by the orchestrator via:
  pct exec <vmid> -- python3 /opt/suyam/email_m365.py

Environment variables read:
  SUYAM_CRED_TEAMS_TENANT_ID      — Azure AD tenant ID (required)
  SUYAM_CRED_TEAMS_CLIENT_ID      — Azure AD app client ID (required)
  SUYAM_CRED_TEAMS_CLIENT_SECRET  — Azure AD app client secret (required)
  SUYAM_CRED_M365_SENDER_USER_ID  — UPN or Object ID of sending mailbox (required)
  SUYAM_STEP_CONFIG_TO            — recipient email address (required)
  SUYAM_STEP_CONFIG_SUBJECT       — email subject (required)
  SUYAM_STEP_INPUT                — email body text (rendered by orchestrator)

Note: client_id and client_secret are the same Azure AD app registration used
for the Teams trigger (D-14). The app registration must have BOTH:
  - ChannelMessage.Read.All (for Teams trigger)
  - Mail.Send (for this email.m365 step)

Security: client_secret is read from env but NEVER echoed to stdout.
All logging to sys.stderr only.
"""

import asyncio
import os
import sys


async def send_email(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    sender_user_id: str,
    to: str,
    subject: str,
    body: str,
) -> None:
    """Send email via Microsoft Graph API sendMail endpoint.

    Uses app-only (client credentials) flow. sender_user_id is required
    because /me endpoint is unavailable without delegated permissions.
    """
    from azure.identity import ClientSecretCredential
    from msgraph import GraphServiceClient
    from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
        SendMailPostRequestBody,
    )
    from msgraph.generated.models.message import Message
    from msgraph.generated.models.item_body import ItemBody
    from msgraph.generated.models.body_type import BodyType
    from msgraph.generated.models.recipient import Recipient
    from msgraph.generated.models.email_address import EmailAddress

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    graph_client = GraphServiceClient(credentials=credential)

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


def main() -> None:
    # ── Read required credentials ────────────────────────────────────────────
    tenant_id: str = os.environ.get("SUYAM_CRED_TEAMS_TENANT_ID", "").strip()
    client_id: str = os.environ.get("SUYAM_CRED_TEAMS_CLIENT_ID", "").strip()
    client_secret: str = os.environ.get("SUYAM_CRED_TEAMS_CLIENT_SECRET", "").strip()
    # IN-01: sender_user_id is step config, not a credential. Read from
    # SUYAM_STEP_CONFIG_SENDER_USER_ID to match the in-process handler convention.
    # Fall back to legacy SUYAM_CRED_M365_SENDER_USER_ID for backward compatibility.
    sender_user_id: str = (
        os.environ.get("SUYAM_STEP_CONFIG_SENDER_USER_ID", "").strip()
        or os.environ.get("SUYAM_CRED_M365_SENDER_USER_ID", "").strip()
    )

    # ── Read step config ─────────────────────────────────────────────────────
    to: str = os.environ.get("SUYAM_STEP_CONFIG_TO", "").strip()
    subject: str = os.environ.get("SUYAM_STEP_CONFIG_SUBJECT", "").strip()
    body: str = os.environ.get("SUYAM_STEP_INPUT", "")

    # ── Validate required inputs ─────────────────────────────────────────────
    missing = []
    if not tenant_id:
        missing.append("SUYAM_CRED_TEAMS_TENANT_ID")
    if not client_id:
        missing.append("SUYAM_CRED_TEAMS_CLIENT_ID")
    if not client_secret:
        missing.append("SUYAM_CRED_TEAMS_CLIENT_SECRET")
    if not sender_user_id:
        missing.append("SUYAM_STEP_CONFIG_SENDER_USER_ID")
    if not to:
        missing.append("SUYAM_STEP_CONFIG_TO")
    if not subject:
        missing.append("SUYAM_STEP_CONFIG_SUBJECT")

    if missing:
        sys.stderr.write(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
        )
        sys.exit(1)

    sys.stderr.write(
        f"[email_m365] sender_user_id={sender_user_id} to={to} subject={subject!r}\n"
    )

    # ── Send email via Graph API ─────────────────────────────────────────────
    try:
        asyncio.run(send_email(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            sender_user_id=sender_user_id,
            to=to,
            subject=subject,
            body=body,
        ))

        # ONLY 'sent' goes to stdout — no credentials, no debug
        print("sent")

    except ImportError as e:
        sys.stderr.write(
            f"FATAL: msgraph-sdk or azure-identity not installed: {e}\n"
            "Rebuild the container image: msgraph-sdk is baked into the NixOS flake via configuration.nix\n"
        )
        sys.exit(1)

    except Exception as e:
        status_code = getattr(e, "response_status_code", None)
        if status_code is not None and status_code >= 500:
            sys.stderr.write(
                f"TRANSIENT: Graph API error (HTTP {status_code}): {e}\n"
            )
            sys.exit(2)  # exit 2 = transient (retryable by orchestrator)
        sys.stderr.write(f"FATAL: Graph API error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
