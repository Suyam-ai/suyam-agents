#!/usr/bin/env python3
"""Container script for teams.poll step.

Polls a Microsoft Teams channel for the latest message via the Graph API
and outputs the message body text to stdout. Intended to be chained into
an ai.summarize or email.m365 step.

Stdout contract: message body text only — nothing else.
All debug, progress, and error messages go to sys.stderr.
Exit 0 on success, non-zero on failure.

Executed by the orchestrator via:
  pct exec <vmid> -- python3 /opt/suyam/teams_poll.py

Environment variables read:
  SUYAM_CRED_TEAMS_TENANT_ID      — Azure AD tenant ID (required)
  SUYAM_CRED_TEAMS_CLIENT_ID      — Azure AD app client ID (required)
  SUYAM_CRED_TEAMS_CLIENT_SECRET  — Azure AD app client secret (required)
  SUYAM_STEP_CONFIG_TEAM_ID       — Teams team ID (required)
  SUYAM_STEP_CONFIG_CHANNEL_ID    — Teams channel ID (required)

Note: ChannelMessage.Read.All requires Microsoft protected API approval.
See docs/teams-setup.md for the approval request URL and setup steps.

Security: client_secret is read from env but NEVER echoed to stdout.
All logging to sys.stderr only.
"""

import asyncio
import os
import sys


async def poll_latest_message(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    team_id: str,
    channel_id: str,
) -> str:
    """Fetch the most recent message body from a Teams channel.

    Returns the plain-text body of the latest message, or an empty string
    if the channel has no messages.
    """
    from azure.identity import ClientSecretCredential
    from msgraph import GraphServiceClient

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    graph_client = GraphServiceClient(credentials=credential)

    # IN-02 fix: fetch only the 1 most recent message ordered by createdDateTime
    # descending. Without $orderby the Graph API returns messages in chronological
    # order (oldest first), making messages.value[0] the oldest, not the latest.
    from msgraph.generated.teams.item.channels.item.messages.messages_request_builder import (  # noqa: PLC0415
        MessagesRequestBuilder,
    )
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=1,
        orderby=["createdDateTime desc"],
    )
    request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )
    messages = await (
        graph_client
        .teams
        .by_team_id(team_id)
        .channels
        .by_channel_id(channel_id)
        .messages
        .get(request_configuration=request_config)
    )

    if not messages or not messages.value:
        sys.stderr.write("[teams_poll] No messages found in channel.\n")
        return ""

    latest = messages.value[0]
    body = latest.body
    if body is None:
        return ""
    # IN-04 fix: Teams messages with HTML body type contain raw HTML tags
    # (<p>, <div>, <at data-id=...>, etc.) which degrade AI summarisation quality.
    # Strip tags and decode HTML entities when content_type indicates HTML.
    import html as _html  # noqa: PLC0415
    import re as _re  # noqa: PLC0415
    content = body.content or ""
    if content and getattr(body, "content_type", None) is not None and "html" in str(body.content_type).lower():
        content = _re.sub(r"<[^>]+>", " ", content)
        content = _html.unescape(content)
        content = " ".join(content.split())  # normalize whitespace
    return content


def main() -> None:
    # ── Read required credentials ────────────────────────────────────────────
    tenant_id: str = os.environ.get("SUYAM_CRED_TEAMS_TENANT_ID", "").strip()
    client_id: str = os.environ.get("SUYAM_CRED_TEAMS_CLIENT_ID", "").strip()
    client_secret: str = os.environ.get("SUYAM_CRED_TEAMS_CLIENT_SECRET", "").strip()

    # ── Read step config ─────────────────────────────────────────────────────
    team_id: str = os.environ.get("SUYAM_STEP_CONFIG_TEAM_ID", "").strip()
    channel_id: str = os.environ.get("SUYAM_STEP_CONFIG_CHANNEL_ID", "").strip()

    # ── Validate required inputs ─────────────────────────────────────────────
    missing = []
    if not tenant_id:
        missing.append("SUYAM_CRED_TEAMS_TENANT_ID")
    if not client_id:
        missing.append("SUYAM_CRED_TEAMS_CLIENT_ID")
    if not client_secret:
        missing.append("SUYAM_CRED_TEAMS_CLIENT_SECRET")
    if not team_id:
        missing.append("SUYAM_STEP_CONFIG_TEAM_ID")
    if not channel_id:
        missing.append("SUYAM_STEP_CONFIG_CHANNEL_ID")

    if missing:
        sys.stderr.write(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
        )
        sys.exit(1)

    sys.stderr.write(
        f"[teams_poll] team_id={team_id} channel_id={channel_id}\n"
    )

    # ── Poll Teams channel ───────────────────────────────────────────────────
    try:
        message_body = asyncio.run(poll_latest_message(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            team_id=team_id,
            channel_id=channel_id,
        ))

        # ONLY message body goes to stdout — no credentials, no debug
        print(message_body)

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
