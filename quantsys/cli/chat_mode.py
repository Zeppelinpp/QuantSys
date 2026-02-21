"""Interactive chat mode for QuantSys."""

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from quantsys.agent.core import Agent
from quantsys.config import get_settings

console = Console()


def start_chat() -> None:
    """Start interactive chat session."""
    settings = get_settings()
    agent = Agent(settings)

    # Welcome message
    console.print(Panel.fit(
        "[bold cyan]QuantSys Agent[/bold cyan]\n"
        "Type your questions or use /commands. Type 'exit' or 'quit' to exit.",
        title="Welcome",
    ))

    # Show available commands
    commands = agent.get_available_commands()
    if commands:
        console.print("[dim]Available commands: " + ", ".join(sorted(commands)) + "[/dim]\n")

    # Chat loop
    while True:
        try:
            # Get user input
            user_input = console.input("[bold green]You:[/bold green] ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "help":
                _show_help(agent)
                continue

            if user_input.lower() == "reset":
                agent.reset()
                console.print("[dim]Conversation reset.[/dim]")
                continue

            # Process input
            with console.status("[dim]Thinking...[/dim]"):
                response = agent.chat(user_input)

            # Display response
            console.print(f"[bold blue]Agent:[/bold blue] ", end="")
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit.[/dim]")
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def _show_help(agent: Agent) -> None:
    """Show help information."""
    help_text = """
## Available Commands

**Slash Commands:**
"""
    commands = agent.get_available_commands()
    for cmd in sorted(commands):
        help_text += f"- `{cmd}` - Execute command\n"

    help_text += """
**Special Commands:**
- `help` - Show this help
- `reset` - Reset conversation
- `exit` or `quit` - Exit chat

**Tips:**
- You can ask natural language questions
- Use @filename to reference files
- Commands can have arguments
"""
    console.print(Markdown(help_text))
