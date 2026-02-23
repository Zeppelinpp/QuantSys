"""Interactive chat mode for QuantSys - Claude Code style interface."""

import re
from pathlib import Path
from typing import List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree

from quantsys.agent.core import Agent
from quantsys.config import get_settings

console = Console()


class CommandLexer(Lexer):
    """Highlights recognized slash commands with a dim blue background."""

    _CMD_RE = re.compile(r"^(/\S+)(.*)")

    def __init__(self, commands: list[str]):
        self.command_names = {cmd.lstrip("/") for cmd in commands}

    def lex_document(self, document):
        def get_line(lineno):
            line = document.lines[lineno]
            if not line.startswith("/"):
                return [("", line)]
            m = self._CMD_RE.match(line)
            if not m:
                return [("", line)]
            cmd_token, rest = m.group(1), m.group(2)
            if cmd_token[1:] in self.command_names:
                result = [("class:slash-cmd", cmd_token)]
                if rest:
                    result.append(("", rest))
                return result
            return [("", line)]

        return get_line


class SlashCommandCompleter(Completer):
    """Completer for slash commands and @ file references."""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.commands = agent.get_available_commands()

    def get_completions(self, document, complete_event):
        text = document.text
        word = document.get_word_under_cursor()

        # Complete @ file references - no background color
        if "@" in text:
            for match in re.finditer(r"@(\S*)", text):
                start, end = match.span(1)
                if start <= document.cursor_position <= end:
                    prefix = match.group(1)
                    for file_path in self._find_files(prefix):
                        # No style parameter = no background color
                        yield Completion(str(file_path), start_position=-len(prefix), style="")
                    break

        # Complete slash commands - match against typed text after the slash
        elif text.startswith("/"):
            typed = text[1:]  # strip the leading slash
            for cmd in self.commands:
                cmd_name = cmd.lstrip("/")
                if cmd_name.startswith(typed):
                    yield Completion(cmd_name, start_position=-len(typed), style="")

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
    """Interactive chat interface."""

    def __init__(self):
        self.settings = get_settings()
        self.agent = Agent(self.settings)
        self.completer = SlashCommandCompleter(self.agent)
        self.lexer = CommandLexer(self.agent.get_available_commands())
        self.session = PromptSession(
            completer=self.completer,
            lexer=self.lexer,
            auto_suggest=AutoSuggestFromHistory(),
            complete_while_typing=True,
            complete_style=CompleteStyle.MULTI_COLUMN,
            style=Style.from_dict({
                'prompt': 'ansigreen bold',
                'slash-cmd': 'bg:#264f78',
                'completion-menu': 'noinherit',
                'completion-menu.completion': 'noinherit',
                'completion-menu.completion.current': 'noinherit reverse',
            })
        )
        self.running = True

    def start(self):
        """Start the chat interface."""
        self._show_welcome()

        while self.running:
            try:
                prompt_fragments = self._build_prompt()

                user_input = self.session.prompt(
                    prompt_fragments,
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

    def _build_prompt(self) -> List:
        """Build plain prompt."""
        return [("ansigreen bold", "quant> ")]

    def _show_welcome(self):
        """Show welcome message."""
        console.print(Panel.fit(
            "[bold cyan]QuantSys Agent[/bold cyan]\n"
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
        if user_input.startswith("/"):
            self._handle_slash_command(user_input)
            return
        self._chat(user_input)

    def _chat(self, user_input: str):
        """Send a message to the agent and render the response."""
        if "@" in user_input:
            user_input = self._expand_file_refs(user_input)
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
            # Try to load skill or execute command
            self._load_skill_or_command(command_line)

    def _load_skill_or_command(self, command_line: str):
        """Load a skill or command, then forward any trailing text as a chat message."""
        parts = command_line.split(None, 1)  # split into command + rest
        command = parts[0].lower()
        trailing = parts[1].strip() if len(parts) > 1 else ""

        # Check if it's a skill command
        skill = self.agent.skills.get_skill_by_command(command)
        if skill:
            try:
                self.agent.load_skill(skill.name)
                console.print(f"[green]⏺[/green] Skill([cyan]{skill.name}[/cyan])")
                console.print(f"  [dim]⎿  Successfully loaded skill[/dim]")
            except Exception as e:
                console.print(f"[red]Error loading skill:[/red] {e}")
                return
            # Forward any trailing question to the agent
            if trailing:
                self._chat(trailing)
            return

        # Check if it's a known command
        if command in self.agent.get_available_commands():
            console.print(f"[green]⏺[/green] Command([cyan]{command}[/cyan])")
            console.print(f"  [dim]⎿  Successfully loaded[/dim]")
            if trailing:
                self._chat(trailing)
            return

        # Unknown command
        console.print(f"[red]Unknown command:[/red] {command}")

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
        console.print("\n[dim]Use [cyan]/<command_name>[/cyan] to load a skill or command[/dim]\n")

    def _show_help(self):
        """Show help information."""
        help_text = """[bold cyan]QuantSys Agent Commands[/bold cyan]

[bold]Slash Commands:[/bold]
  [cyan]/skills[/cyan]    - List available skills
  [cyan]/help[/cyan]      - Show this help
  [cyan]/clear[/cyan]     - Clear the screen
  [cyan]/reset[/cyan]     - Reset conversation
  [cyan]/quit[/cyan]      - Exit the chat

[bold]Load Skills:[/bold]
  [cyan]/<skill_name>[/cyan]   - Load a skill into agent context

[bold]File References:[/bold]
  [cyan]@filename[/cyan]  - Inline file content into your message (Tab to autocomplete)

[bold]Examples:[/bold]
  quant> [green]How do I create a momentum strategy?[/green]
  quant> [cyan]/backtest[/cyan]
  quant> [green]Analyze @strategies/momentum.py[/green]

[bold]Tips:[/bold]
- Press Tab for autocomplete on commands and files
- @file reads and inlines the file so the agent sees its content
- /skill loads a skill's documentation into the agent context"""

        console.print(Panel(help_text, title="Help", border_style="cyan"))

    def _expand_file_refs(self, text: str) -> str:
        """Expand @ file references, inlining file content into the message."""
        def replace_ref(match):
            ref = match.group(1)
            files = self._find_files(ref)
            if not files:
                return match.group(0)
            if len(files) > 1:
                console.print(f"[dim]Multiple matches for @{ref}:[/dim]")
                for i, f in enumerate(files[:5], 1):
                    console.print(f"  [cyan]{i}.[/cyan] {f}")
                return match.group(0)
            # Single match — inline the file content
            file_path = files[0]
            try:
                content = file_path.read_text(encoding="utf-8")
                console.print(f"[dim]⎿  Read {file_path} ({len(content)} chars)[/dim]")
                return f"[File: {file_path}]\n```\n{content}\n```"
            except Exception as e:
                console.print(f"[red]Could not read {file_path}:[/red] {e}")
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
