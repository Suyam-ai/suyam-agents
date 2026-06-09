#!/usr/bin/env python3
"""Container agent script for ai.summarize step.

Supports pydantic-ai (preferred) with direct-SDK fallback for groq and anthropic.
Stdout contract: ONLY the summary text. Stderr for all debug/errors. Exit 0 on success.

Executed by the orchestrator via:
  pct exec <vmid> -- python3 /opt/suyam/ai_summarize.py
"""

import os
import sys

_PROVIDER_ENV_MAP: dict[str, tuple[str, str]] = {
    "anthropic":     ("SUYAM_CRED_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    "groq":          ("SUYAM_CRED_GROQ_API_KEY",      "GROQ_API_KEY"),
    "openai":        ("SUYAM_CRED_OPENAI_API_KEY",     "OPENAI_API_KEY"),
    "google-gla":    ("SUYAM_CRED_GOOGLE_API_KEY",     "GOOGLE_API_KEY"),
    "google-vertex": ("SUYAM_CRED_GOOGLE_API_KEY",     "GOOGLE_API_KEY"),
}


def _run_via_groq(model_name: str, system_prompt: str, input_text: str, api_key: str) -> str:
    from groq import Groq  # type: ignore[import]
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ],
        model=model_name,
    )
    return completion.choices[0].message.content or ""


def _run_via_anthropic(model_name: str, system_prompt: str, input_text: str, api_key: str) -> str:
    import anthropic  # type: ignore[import]
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model_name,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": input_text}],
    )
    return message.content[0].text


def _run_via_pydantic_ai(model_str: str, system_prompt: str, input_text: str) -> str:
    from pydantic_ai import Agent  # type: ignore[import]
    agent = Agent(model=model_str, system_prompt=system_prompt)
    result = agent.run_sync(input_text)
    return result.output


def main() -> None:
    input_text = os.environ.get("SUYAM_STEP_INPUT", "").strip()
    if not input_text:
        sys.stderr.write("ERROR: SUYAM_STEP_INPUT is empty\n")
        sys.exit(1)

    model_str = os.environ.get("SUYAM_STEP_CONFIG_MODEL", "anthropic:claude-sonnet-4-6")
    if ":" not in model_str:
        model_str = f"anthropic:{model_str}"

    provider = model_str.split(":")[0].lower()
    model_name = model_str.split(":", 1)[1]

    provider_entry = _PROVIDER_ENV_MAP.get(provider)
    if provider_entry is None:
        sys.stderr.write(f"ERROR: unknown provider '{provider}'. Supported: {', '.join(_PROVIDER_ENV_MAP)}\n")
        sys.exit(1)

    cred_key, std_env_var = provider_entry
    api_key = os.environ.get(cred_key, "")
    if not api_key:
        sys.stderr.write(f"ERROR: {cred_key} not set\n")
        sys.exit(1)

    os.environ[std_env_var] = api_key  # T-04-10: never echoed to stdout

    system_prompt = os.environ.get(
        "SUYAM_STEP_CONFIG_PROMPT",
        "Summarize the following text concisely in 2-3 sentences.",
    )

    sys.stderr.write(f"[ai_summarize] model={model_str} input_length={len(input_text)} chars\n")

    try:
        # Try pydantic-ai first (baked into NixOS image via configuration.nix)
        try:
            output = _run_via_pydantic_ai(model_str, system_prompt, input_text)
            sys.stderr.write("[ai_summarize] used pydantic-ai path\n")
        except ImportError:
            sys.stderr.write(
                "[ai_summarize] pydantic-ai unavailable — using direct SDK\n"
                "Container image may need rebuild: nix build .#packages.x86_64-linux.proxmox-lxc\n"
            )
            if provider == "groq":
                output = _run_via_groq(model_name, system_prompt, input_text, api_key)
            elif provider == "anthropic":
                output = _run_via_anthropic(model_name, system_prompt, input_text, api_key)
            else:
                sys.stderr.write(f"FATAL: no direct-SDK fallback for provider '{provider}' — install pydantic-ai\n")
                sys.exit(1)

        print(output)  # stdout contract: only the summary

    except Exception as e:
        # IN-02: Distinguish transient (5xx, 429) from fatal errors so the
        # orchestrator can retry rate-limit/server errors instead of treating
        # all AI API failures as permanent. Exit 2 = transient, 1 = fatal.
        status_code = getattr(e, "status_code", None) or getattr(e, "response_status_code", None)
        if status_code is not None and (status_code >= 500 or status_code == 429):
            sys.stderr.write(f"TRANSIENT: AI API error (HTTP {status_code}): {e}\n")
            sys.exit(2)
        sys.stderr.write(f"FATAL: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
