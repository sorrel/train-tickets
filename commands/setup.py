"""
Setup and status commands.
"""

import textwrap

import click


class ColouredGroup(click.Group):
    """Click group with coloured command listing."""

    def format_commands(self, ctx, formatter):
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            help_text = cmd.get_short_help_str(limit=150)
            commands.append((subcommand, help_text))

        if commands:
            col_width = max(len(name) for name, _ in commands) + 2
            help_col = 4 + col_width
            help_indent = " " * help_col
            available = max(formatter.width - help_col, 20)
            with formatter.section("Commands"):
                for name, help_text in commands:
                    padding = " " * (col_width - len(name))
                    name_str = click.style(name, fg="cyan")
                    lines = textwrap.wrap(help_text, width=available)
                    first = lines[0] if lines else ""
                    rest = ("\n" + help_indent).join(lines[1:])
                    full = (first + "\n" + help_indent + rest) if rest else first
                    formatter.write(f"    {name_str}{padding}{full}\n")


@click.command("status")
def status_command():
    """Show connection status and configuration."""
    click.echo(click.style("Train Tickets CLI", fg="green"))
    click.echo("  Status: ready (no authentication required)")
