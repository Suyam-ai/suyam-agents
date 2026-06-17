"""AI integration step handler.

AISummarizeHandler is registered for step type "ai.summarize".

In production workflows, ai.summarize steps are executed inside an ephemeral
LXC container (common-agent) via ScriptDispatcher.dispatch() in runner.py.
This in-process handler:
  - Satisfies the pluggy registry so validate-step-types can confirm the step type is known
  - Implements the full PydanticAI Agent call so it can be used directly in
    test/mock contexts where a container is not available

The actual production execution path is:
  runner.py execute_workflow()
    → self._dispatcher.dispatch()
    → run_container_lifecycle()
    → pct exec: python3 /opt/suyam/ai_summarize.py

D-15 (RESEARCH.md Pitfall 4): Agent is instantiated INSIDE run() per call — never
as a module-level singleton. PydanticAI Agent objects are not intended to be shared
across calls with different models or system prompts.

pydantic-ai is lazy-imported via try/except — the package is baked into the
NixOS LXC image via buildPythonPackage in agents/common-agent/configuration.nix.
The try/except guard below is kept as a defensive fallback for local dev.
"""

import pluggy

from suyam_agents.exceptions import FatalError, TransientError

hookimpl = pluggy.HookimplMarker("suyam")

# pydantic-ai is baked into the NixOS LXC image via buildPythonPackage in
# agents/common-agent/configuration.nix. The try/except guard below is kept
# as a defensive fallback (e.g., running outside the container during local dev).
try:
    from pydantic_ai import Agent
    from pydantic_ai.exceptions import (
        UnexpectedModelBehavior,
        UsageLimitExceeded,
        UserError,
    )
    _PYDANTIC_AI_AVAILABLE = True
except ImportError:
    _PYDANTIC_AI_AVAILABLE = False
    Agent = None  # type: ignore[assignment,misc]
    UnexpectedModelBehavior = None  # type: ignore[assignment,misc]
    UsageLimitExceeded = None  # type: ignore[assignment,misc]
    UserError = None  # type: ignore[assignment,misc]


class AISummarizeHandler:
    """Step handler for 'ai.summarize' step type.

    Instantiates a PydanticAI Agent per call (D-15 — no module-level singleton).
    Model and system_prompt are built from step.config on each run() call.

    In production, this handler is never called directly — execute_workflow()
    routes ai.* steps to dispatch_step_to_container() which runs the container
    script agents/common-agent/scripts/ai_summarize.py inside an ephemeral LXC.
    This handler is available for unit tests (mock pydantic_ai.Agent) and direct
    CLI usage outside container context.
    """

    STEP_TYPE = "ai"
    DISPLAY_NAME = "AI Step"
    DESCRIPTION = "Runs a Claude/AI model call on provided input"
    AGENT_TYPE = "ai"
    VERSION = "1.0.0"
    PARAMS_SCHEMA = {"type": "object", "properties": {"model": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["prompt"]}

    def run(self, step: object, context: dict) -> str:
        """Execute an ai.summarize step using PydanticAI.

        Reads model, prompt, and input from step.config (already Jinja2-rendered
        by runner._render_config before this method is called).

        Args:
            step: Duck-typed step object with rendered config dict containing optional keys:
                  - model: Claude model name without provider prefix (default: "claude-sonnet-4-6")
                  - prompt: System prompt string (default: built-in summarizer prompt)
                  - input: Text to summarize (falls back to context["trigger"]["message"])
            context: Jinja2 execution context with "steps", "trigger", "run" keys.

        Returns:
            Summary string from result.output.

        Raises:
            FatalError: No input text available; UsageLimitExceeded; UserError (misconfiguration);
                        APIStatusError with status_code < 500.
            TransientError: UnexpectedModelBehavior (bad model response);
                            APIStatusError with status_code >= 500.
        """
        if not _PYDANTIC_AI_AVAILABLE:
            raise FatalError(
                "ai.summarize: pydantic-ai is not available. "
                "Rebuild the container image: nix build agents/common-agent#packages.x86_64-linux.proxmox-lxc"
            )

        # --- Build call parameters from step config (all already Jinja2-rendered) ---
        model_name: str = step.config.get("model", "claude-sonnet-4-6")  # type: ignore[attr-defined]
        model_string: str = f"anthropic:{model_name}"

        system_prompt: str = step.config.get(  # type: ignore[attr-defined]
            "prompt",
            "Summarize the following text concisely in 2-3 sentences.",
        )

        input_text: str = step.config.get(  # type: ignore[attr-defined]
            "input",
            context.get("trigger", {}).get("message", ""),
        )

        if not input_text:
            raise FatalError(
                "ai.summarize: no input text — set step.config.input or ensure "
                "trigger.message is populated"
            )

        # D-15: Agent instantiated per call — not a module-level singleton.
        # Each call may have a different model or system_prompt from step config.
        agent = Agent(model=model_string, system_prompt=system_prompt)

        try:
            result = agent.run_sync(input_text)
            return result.output  # PydanticAI v1.x API — use .output (not .result or .data)
        except UnexpectedModelBehavior as e:  # type: ignore[misc]
            raise TransientError(
                f"AI model returned unusable response: {e}"
            ) from e
        except UsageLimitExceeded as e:  # type: ignore[misc]
            raise FatalError(
                f"AI usage limit exceeded: {e}"
            ) from e
        except UserError as e:  # type: ignore[misc]
            raise FatalError(
                f"AI handler misconfiguration: {e}"
            ) from e
        except Exception as e:
            # APIStatusError and other HTTP-level errors carry status_code
            status_code = getattr(e, "status_code", None)
            if status_code is not None and status_code >= 500:
                raise TransientError(
                    f"AI API transient error (HTTP {status_code}): {e}"
                ) from e
            raise FatalError(
                f"AI API error (HTTP {status_code if status_code else 'unknown'}): {e}"
            ) from e


class AiIntegration:
    """Pluggy plugin class for the AI integration.

    Provides AGENT_TYPE_MAP for AgentTypeResolver and registers step handlers
    via the @hookimpl register_handlers method (REFACTOR-02).
    """

    AGENT_TYPE_MAP: dict[str, str] = {"ai": "common-agent"}
    STEP_HANDLERS: list = [AISummarizeHandler]

    @hookimpl
    def register_handlers(self, pm: pluggy.PluginManager) -> None:
        """Register AISummarizeHandler with the plugin manager."""
        pm.register(AISummarizeHandler())


plugin = AiIntegration()
