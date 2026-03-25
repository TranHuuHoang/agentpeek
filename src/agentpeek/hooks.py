"""Install/uninstall AgentPeek hooks into ~/.claude/settings.json."""

from __future__ import annotations

import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

HOOK_EVENTS = [
    "PreToolUse",
    "PostToolUse",
    "SubagentStart",
    "SubagentStop",
    "Stop",
]

AGENTPEEK_MARKER = "agentpeek.jsonl"


def _make_hook(event: str) -> dict:
    return {
        "type": "command",
        "command": f'jq -c \'{{hook:"{event}"}} + .\' >> /tmp/agentpeek.jsonl',
        "async": True,
    }


def install_hooks() -> bool:
    """Merge AgentPeek hooks into ~/.claude/settings.json. Returns True if changes were made."""
    settings = _read_settings()
    hooks = settings.setdefault("hooks", {})
    changed = False

    for event in HOOK_EVENTS:
        event_hooks = hooks.setdefault(event, [])

        # Check if our hook already exists
        already_installed = False
        for entry in event_hooks:
            # Handle both flat and nested formats
            hook_list = entry.get("hooks", [entry]) if isinstance(entry, dict) else []
            for h in hook_list:
                if isinstance(h, dict) and AGENTPEEK_MARKER in h.get("command", ""):
                    already_installed = True
                    break
            if already_installed:
                break

        if not already_installed:
            event_hooks.append({"hooks": [_make_hook(event)]})
            changed = True

    if changed:
        _write_settings(settings)
    return changed


def uninstall_hooks() -> bool:
    """Remove AgentPeek hooks from ~/.claude/settings.json. Returns True if changes were made."""
    settings = _read_settings()
    hooks = settings.get("hooks", {})
    changed = False

    for event in HOOK_EVENTS:
        event_hooks = hooks.get(event, [])
        filtered = []
        for entry in event_hooks:
            hook_list = entry.get("hooks", [entry]) if isinstance(entry, dict) else []
            is_ours = any(
                isinstance(h, dict) and AGENTPEEK_MARKER in h.get("command", "")
                for h in hook_list
            )
            if not is_ours:
                filtered.append(entry)
        if len(filtered) != len(event_hooks):
            hooks[event] = filtered
            changed = True

    # Clean up empty event arrays
    for event in list(hooks.keys()):
        if not hooks[event]:
            del hooks[event]

    if changed:
        _write_settings(settings)
    return changed


def hooks_installed() -> bool:
    """Check if AgentPeek hooks are present in settings."""
    settings = _read_settings()
    hooks = settings.get("hooks", {})
    for event in HOOK_EVENTS:
        found = False
        for entry in hooks.get(event, []):
            hook_list = entry.get("hooks", [entry]) if isinstance(entry, dict) else []
            for h in hook_list:
                if isinstance(h, dict) and AGENTPEEK_MARKER in h.get("command", ""):
                    found = True
                    break
            if found:
                break
        if not found:
            return False
    return True


def _read_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
