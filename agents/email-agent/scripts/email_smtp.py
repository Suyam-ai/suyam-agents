#!/usr/bin/env python3
"""Container script for email.smtp step.

Reads credentials and config from environment variables, sends email via
smtplib, prints 'sent' to stdout on success.

Stdout contract: ONLY 'sent' on success — nothing else.
All debug, progress, and error messages go to sys.stderr.
Exit 0 on success, non-zero on failure.

Executed by the orchestrator via:
  pct exec <vmid> -- python3 /opt/suyam/email_smtp.py

Environment variables read:
  SUYAM_CRED_SMTP_HOST      — SMTP server hostname (required)
  SUYAM_CRED_SMTP_PORT      — SMTP server port, default 587 (str, cast to int)
  SUYAM_CRED_SMTP_USERNAME  — SMTP username / From email address (required)
  SUYAM_CRED_SMTP_PASSWORD  — SMTP password (required; NEVER echoed to stdout)
  SUYAM_STEP_CONFIG_TO      — recipient email address (required)
  SUYAM_STEP_CONFIG_SUBJECT — email subject (required)
  SUYAM_STEP_INPUT          — email body text (rendered by orchestrator)

Security (T-04-13): SUYAM_CRED_SMTP_PASSWORD is read from env but NEVER
printed to stdout. All logging goes to sys.stderr only.

TLS selection (D-13):
  - port 465 → SMTP_SSL (implicit TLS)
  - any other port (typically 587) → SMTP + STARTTLS
"""

import os
import smtplib
import sys
from email.message import EmailMessage


def main() -> None:
    # ── Read required credentials ────────────────────────────────────────────
    host: str = os.environ.get("SUYAM_CRED_SMTP_HOST", "").strip()
    port_str: str = os.environ.get("SUYAM_CRED_SMTP_PORT", "587").strip()
    username: str = os.environ.get("SUYAM_CRED_SMTP_USERNAME", "").strip()
    password: str = os.environ.get("SUYAM_CRED_SMTP_PASSWORD", "").strip()

    # ── Read step config ─────────────────────────────────────────────────────
    to: str = os.environ.get("SUYAM_STEP_CONFIG_TO", "").strip()
    subject: str = os.environ.get("SUYAM_STEP_CONFIG_SUBJECT", "").strip()
    body: str = os.environ.get("SUYAM_STEP_INPUT", "")

    # ── Validate required inputs ─────────────────────────────────────────────
    missing = []
    if not host:
        missing.append("SUYAM_CRED_SMTP_HOST")
    if not username:
        missing.append("SUYAM_CRED_SMTP_USERNAME")
    if not password:
        missing.append("SUYAM_CRED_SMTP_PASSWORD")
    if not to:
        missing.append("SUYAM_STEP_CONFIG_TO")
    if not subject:
        missing.append("SUYAM_STEP_CONFIG_SUBJECT")

    if missing:
        sys.stderr.write(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
        )
        sys.exit(1)

    try:
        port: int = int(port_str)
    except ValueError:
        sys.stderr.write(
            f"ERROR: SUYAM_CRED_SMTP_PORT must be an integer, got: {port_str!r}\n"
        )
        sys.exit(1)

    sys.stderr.write(
        f"[email_smtp] host={host} port={port} to={to} subject={subject!r}\n"
    )

    # ── Build EmailMessage ───────────────────────────────────────────────────
    msg = EmailMessage()
    msg["From"] = username
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    # ── Send with port-based TLS detection (D-13) ────────────────────────────
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
                smtp.ehlo()   # RFC 3207: re-identify after TLS upgrade
                smtp.login(username, password)
                smtp.send_message(msg)

        # T-04-13: ONLY 'sent' goes to stdout — no credentials, no debug
        print("sent")

    except smtplib.SMTPRecipientsRefused as e:
        sys.stderr.write(f"FATAL: recipients refused by server: {e}\n")
        sys.exit(1)

    except smtplib.SMTPDataError as e:
        sys.stderr.write(f"FATAL: SMTP data error (message rejected): {e}\n")
        sys.exit(1)

    except smtplib.SMTPServerDisconnected as e:
        sys.stderr.write(f"TRANSIENT: server disconnected unexpectedly: {e}\n")
        sys.exit(2)  # exit 2 = transient (retryable by orchestrator)

    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
