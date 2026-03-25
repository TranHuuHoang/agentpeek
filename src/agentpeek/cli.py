"""CLI entry point — `agentpeek` command."""

from __future__ import annotations

import webbrowser

import click
import uvicorn


@click.group(invoke_without_command=True)
@click.option("--port", default=8099, help="Server port", show_default=True)
@click.option("--no-browser", is_flag=True, help="Don't open browser on start")
@click.option("--install-hooks", is_flag=True, help="Install hooks and exit")
@click.option("--uninstall", is_flag=True, help="Remove hooks and exit")
@click.pass_context
def main(ctx: click.Context, port: int, no_browser: bool, install_hooks: bool, uninstall: bool) -> None:
    """AgentPeek — Real-time observability for Claude Code agents."""
    if ctx.invoked_subcommand is not None:
        return

    from agentpeek.hooks import install_hooks as do_install, uninstall_hooks, hooks_installed

    if uninstall:
        if uninstall_hooks():
            click.echo("Hooks removed from ~/.claude/settings.json")
        else:
            click.echo("No hooks to remove")
        return

    if install_hooks:
        if do_install():
            click.echo("Hooks installed in ~/.claude/settings.json")
        else:
            click.echo("Hooks already installed")
        return

    # Default: install hooks + start server
    if do_install():
        click.echo("Hooks installed in ~/.claude/settings.json")
    elif hooks_installed():
        click.echo("Hooks already installed")

    if not no_browser:
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    uvicorn.run(
        "agentpeek.server:app",
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
