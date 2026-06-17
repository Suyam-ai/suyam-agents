"""Teams integration step handler.

TeamsStepHandler is registered for step type "teams.channel_message".
At runtime, Teams steps are executed inside an ephemeral LXC container via
ScriptDispatcher.dispatch() in runner.py — this in-process handler is a
safety guard that raises FatalError if ever called directly.

Pluggy pattern: importing this module and calling plugin.register_handlers(pm)
registers TeamsStepHandler with the plugin manager (REFACTOR-02).

Note: TeamsChannelMessageTrigger (trigger/polling logic) is NOT migrated here —
it implements TriggerHandler (poll/trigger lifecycle) and depends on
suyam.integrations.repository for delta token persistence, so it stays in core
(CONTEXT.md D-06). This module contains only the step handler.
"""

import pluggy

from suyam_agents.exceptions import FatalError

hookimpl = pluggy.HookimplMarker("suyam")


class TeamsStepHandler:
    """Step handler stub for 'teams.*' step types.

    Teams steps are dispatched to an ephemeral LXC container at runtime.
    This handler is registered so the step type is known to the pluggy registry
    (e.g. for validate-step-types), but calling run() directly is an error.
    """

    STEP_TYPE = "teams"
    DISPLAY_NAME = "Microsoft Teams"
    DESCRIPTION = "Polls a Microsoft Teams channel for messages"
    AGENT_TYPE = "teams"
    VERSION = "1.0.0"
    PARAMS_SCHEMA = {"type": "object", "properties": {"channel_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["channel_id"]}

    def run(self, step: object, context: dict) -> str:
        """Raise FatalError — Teams steps must run in an LXC container.

        This method should never be called in normal execution flow.
        execute_workflow() calls self._dispatcher.dispatch() instead.

        Raises:
            FatalError: Always raised to prevent accidental in-process execution.
        """
        raise FatalError(
            "teams steps run inside LXC container — this in-process handler should never be "
            "called directly. Use ScriptDispatcher.dispatch()."
        )


class TeamsIntegration:
    """Pluggy plugin class for the Teams integration.

    Provides AGENT_TYPE_MAP for AgentTypeResolver and registers step handlers
    via the @hookimpl register_handlers method (REFACTOR-02).
    """

    AGENT_TYPE_MAP: dict[str, str] = {"teams": "teams-email-agent"}
    STEP_HANDLERS: list = [TeamsStepHandler]

    @hookimpl
    def register_handlers(self, pm: pluggy.PluginManager) -> None:
        """Register TeamsStepHandler with the plugin manager."""
        pm.register(TeamsStepHandler())


plugin = TeamsIntegration()
