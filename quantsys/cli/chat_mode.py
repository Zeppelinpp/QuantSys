"""Interactive chat mode for QuantSys - Claude Code style interface."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from quantsys.agent.core import Agent
from quantsys.config import get_settings

console = Console()


class SlashCommandCompleter(Completer):
    """Completer for slash commands and @ file references."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.commands = agent.get_available_commands()
        
    def get_completions(self, document, complete_event):
        text = document.text
        word = document.get_word_under_cursor()
        
        # Complete @ file references
        if "@" in text:
            # Find the word containing @
            for match in re.finditer(r"@(\S*)", text):
                start, end = match.span(1)
                if start <= document.cursor_position <= end:
                    prefix = match.group(1)
                    for file_path in self._find_files(prefix):
                        yield Completion(str(file_path), start_position=-len(prefix))
                    break
        
        # Complete slash commands
        elif text.startswith("/"):
            for cmd in self.commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
    
    def _find_files(self, prefix: str) -> List[Path]:
        """Find files matching prefix using ripgrep-like search."""
        files = []
        search_paths = [Path("."), Path("quantsys"), Path("strategies")]
        
        for path in search_paths:
            if not path.exists():
                continue
            try:
                for file in path.rglob("*.py"):
                    if prefix.lower() in file.name.lower() or prefix.lower() in str(file).lower():
                        files.append(file)
                        if len(files) >= 10:
                            break
            except PermissionError:
                continue
        
        return files[:10]


class ChatInterface:
    """Claude Code-style chat interface."""
    
    def __init__(self):
        self.settings = get_settings()
        self.agent = Agent(self.settings)
        self.session = PromptSession(
            completer=SlashCommandCompleter(self.agent),
            auto_suggest=AutoSuggestFromHistory(),
            style=Style.from_dict({
                'prompt': 'ansigreen bold',
                'command': 'ansicyan',
            })
        )
        self.running = True
        
    def start(self):
        """Start the chat interface."""
        self._show_welcome()
        
        while self.running:
            try:
                # Get input with syntax highlighting prompt
                user_input = self.session.prompt(
                    [("class:prompt", "quant> ")],
                    multiline=False,
                ).strip()
                
                if not user_input:
                    continue
                    
                # Handle special commands
                if user_input.lower() in ("exit", "quit", "q"):
                    self._show_goodbye()
                    break
                
                # Process the input
                self._process_input(user_input)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]^C[/yellow] (Interrupt, use Ctrl+D or 'exit' to quit)")
                continue
            except EOFError:
                self._show_goodbye()
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    
    def _show_welcome(self):
        """Show welcome message."""
        console.print(Panel.fit(
            "[bold cyan]QuantSys Agent[/bold cyan] - Claude Code Style\n"
            "[dim]Slash commands[/dim] [cyan]/help[/cyan] • [dim]File refs[/dim] [cyan]@file[/cyan] • [dim]Skills[/dim] [cyan]/skills[/cyan]\n"
            "Type [yellow]exit[/yellow] or [yellow]/quit[/yellow] to exit",
            title="🚀 Welcome",
            border_style="cyan"
        ))
    
    def _show_goodbye(self):
        """Show goodbye message."""
        console.print("\n[dim]👋 Goodbye![/dim]\n")
    
    def _process_input(self, user_input: str):
        """Process user input."""
        # Check for slash commands
        if user_input.startswith("/"):
            self._handle_slash_command(user_input)
            return
        
        # Handle @ file references
        if "@" in user_input:
            user_input = self._expand_file_refs(user_input)
        
        # Regular chat
        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            try:
                response = self.agent.chat(user_input)
                self._render_response(response)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    
    def _handle_slash_command(self, command_line: str):
        """Handle slash commands like /skills, /help, etc."""
        parts = command_line.split()
        command = parts[0].lower()
        args = parts[1:]
        
        # Built-in commands
        if command == "/skills":
            self._show_skills()
        elif command == "/help":
            self._show_help()
        elif command == "/quit":
            self._show_goodbye()
            self.running = False
        elif command == "/clear":
            console.clear()
        elif command == "/reset":
            self.agent.reset()
            console.print("[dim]🔄 Conversation reset[/dim]")
        else:
            # Try to execute skill command
            self._execute_skill_command(command_line)
    
    def _show_skills(self):
        """Show available skills in a tree view."""
        skills = self.agent.skills.list_skills()
        
        if not skills:
            console.print("[dim]No skills found[/dim]")
            return
        
        tree = Tree("[bold cyan]Available Skills[/bold cyan]")
        
        for skill in skills:
            skill_branch = tree.add(f"[green]{skill.name}[/green]")
            skill_branch.add(f"[dim]{skill.description}[/dim]")
            if skill.commands:
                cmds = ", ".join(skill.commands)
                skill_branch.add(f"[cyan]Commands:[/cyan] {cmds}")
        
        console.print(tree)
        console.print("\n[dim]Use [cyan]/load <skill_name>[/cyan] to load a skill[/dim]\n")
    
    def _show_help(self):
        """Show help information."""
        help_text = """[bold cyan]QuantSys Agent Commands[/bold cyan]

[bold]Slash Commands:[/bold]
  [cyan]/skills[/cyan]    - List available skills
  [cyan]/help[/cyan]      - Show this help
  [cyan]/clear[/cyan]     - Clear the screen  
  [cyan]/reset[/cyan]     - Reset conversation
  [cyan]/quit[/cyan]      - Exit the chat

[bold]File References:[/bold]
  [cyan]@filename[/cyan]  - Reference a file (autocomplete with Tab)
  [cyan]@strat<Tab>[/cyan] - Will find strategy files

[bold]Examples:[/bold]
  quant> [green]How do I create a momentum strategy?[/green]
  quant> [cyan]/backtest[/cyan] [green]@strategies/momentum.py --start 2024-01-01[/green]
  quant> [green]What is the Sharpe ratio of my portfolio?[/green]

[bold]Tips:[/bold]
- Press Tab for autocomplete on commands and files
- Use @ to quickly reference strategy files
- Skills provide additional commands like /backtest, /optimize"""
        
        console.print(Panel(help_text, title="Help", border_style="cyan"))
    
    def _expand_file_refs(self, text: str) -> str:
        """Expand @ file references in text."""
        def replace_ref(match):
            ref = match.group(1)
            files = self._find_files(ref)
            if files:
                # If we found a unique match, return full path
                if len(files) == 1:
                    return str(files[0])
                # Otherwise show options
                console.print(f"[dim]Multiple matches for @{ref}:[/dim]")
                for i, f in enumerate(files[:5], 1):
                    console.print(f"  [cyan]{i}.[/cyan] {f}")
                return match.group(0)
            return match.group(0)
        
        return re.sub(r"@(\S+)", replace_ref, text)
    
    def _find_files(self, pattern: str) -> List[Path]:
        """Find files matching pattern."""
        files = []
        search_paths = [Path("."), Path("quantsys"), Path("strategies")]
        
        for path in search_paths:
            if not path.exists():
                continue
            try:
                for file in path.rglob("*"):
                    if file.is_file() and pattern.lower() in file.name.lower():
                        files.append(file)
            except PermissionError:
                continue
        
        return files[:10]
    
    def _execute_skill_command(self, command_line: str):
        """Execute a skill-based slash command."""
        # This would integrate with the skill system
        response = self.agent._handle_command(command_line)
        console.print(f"[bold blue]Agent:[/bold blue] {response}")
    
    def _render_response(self, response: str):
        """Render agent response with markdown support."""
        # Check if response contains code blocks
        if "```" in response:
            # Split and render code blocks with syntax highlighting
            parts = response.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 0:
                    # Regular text
                    if part.strip():
                        console.print(Markdown(part))
                else:
                    # Code block
                    lines = part.split("\n", 1)
                    lang = lines[0].strip() if lines else ""
                    code = lines[1] if len(lines) > 1 else part
                    
                    syntax = Syntax(code, lang or "python", theme="monokai", line_numbers=True)
                    console.print(syntax)
        else:
            console.print(Markdown(response))


def start_chat() -> None:
    """Start interactive chat session."""
    interface = ChatInterface()
    interface.start()
