"""Agent core for QuantSys."""

from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from quantsys.config import Settings, get_settings

from .context_manager import ContextManager
from .llm_client import LLMClient
from .skill_registry import SkillRegistry


class Agent:
    """QuantSys Agent for natural language interaction."""

    SYSTEM_PROMPT = """You are QuantSys Agent — a senior quantitative analyst and trading system expert \
specializing in A-share (China) markets.

## Identity & Expertise

You have deep knowledge in:
- Factor investing: WorldQuant 101 alphas, Fama-French factors, Barra risk model concepts
- Technical analysis: price-volume patterns, momentum, mean-reversion, volatility regimes
- A-share specifics: T+1 settlement, 10% daily price limit (20% for ChiNext/STAR), \
lot size 100 shares, stamp duty 0.05% on sells, transfer fee 0.001%, commission ~0.03% (min 5 yuan)
- Backtest methodology: lookahead bias prevention, survivorship bias, overfitting risks, \
walk-forward validation, out-of-sample testing
- Portfolio construction: position sizing, risk budgeting, sector diversification

## Behavior Guidelines

- Be precise with numbers: returns as percentages, Sharpe to 2 decimals, drawdown as percentage
- Always warn about overfitting when optimization results look too good (Sharpe > 3, etc.)
- Suggest benchmark comparison (CSI 300 / CSI 500) when presenting backtest results
- Prefer simple, robust strategies over complex models — complexity must justify itself
- Proactively check data quality and coverage before backtesting
- Communicate in the user's language (Chinese or English)

## Available Commands
{commands}

## Workflow

1. Understand intent: research, backtest, generate strategy, factor analysis, or general question
2. Select the appropriate skill/command
3. Gather required parameters — ask if anything is missing
4. Execute and present results with actionable interpretation
5. Suggest logical next steps (optimize? different factors? compare with benchmark?)"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize Agent."""
        self.settings = settings or get_settings()
        self.context = ContextManager()
        self.skills = SkillRegistry()
        self.llm = LLMClient(self.settings)

        # Scan for skills
        self._load_skills()

    def _load_skills(self) -> None:
        """Load skills from default and user directories."""
        skill_paths = [
            Path(__file__).parent.parent / "skills",
            Path("user_skills"),
        ]
        self.skills.scan_skills(skill_paths)

        # Add system message with available commands
        commands = self.skills.list_commands()
        commands_str = "\n".join(f"  {cmd}" for cmd in sorted(commands.keys()))

        system_prompt = self.SYSTEM_PROMPT.format(commands=commands_str)
        self.context.add_message("system", system_prompt)

    def chat(self, user_input: str) -> str:
        """Process user input and return response.

        Args:
            user_input: User's message

        Returns:
            Agent's response
        """
        # Check for slash commands
        if user_input.startswith("/"):
            return self._handle_command(user_input)

        # Regular chat - use LLM
        if not self.llm.is_available():
            return "LLM not available. Please set ANTHROPIC_API_KEY in .env"

        self.context.add_message("user", user_input)

        try:
            response = self.llm.chat(
                messages=self.context.get_context(),
                max_tokens=4000,
            )
            self.context.add_message("assistant", response)
            return response
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Error: {e}"

    def _handle_command(self, command_line: str) -> str:
        """Handle slash commands.

        Args:
            command_line: Command line starting with /

        Returns:
            Command output
        """
        parts = command_line.split()
        command = parts[0]
        args = parts[1:]

        # Find skill for command
        skill = self.skills.get_skill_by_command(command)
        if not skill:
            return f"Unknown command: {command}"

        # Load full skill documentation
        try:
            skill_doc = self.skills.load_full_skill(skill.name)
        except Exception as e:
            logger.error(f"Failed to load skill {skill.name}: {e}")
            return f"Error loading skill: {e}"

        # For now, return skill info
        # In full implementation, this would parse args and execute
        return f"Command: {command}\nSkill: {skill.name}\nDescription: {skill.description}"

    def load_skill(self, skill_name: str) -> None:
        """Inject a skill's full documentation into the conversation context."""
        skill_doc = self.skills.load_full_skill(skill_name)
        self.context.add_message("system", f"Skill loaded: {skill_name}\n\n{skill_doc}")

    def get_available_commands(self) -> List[str]:
        """Get list of available commands."""
        return list(self.skills.list_commands().keys())

    def reset(self) -> None:
        """Reset conversation context."""
        self.context.clear()
        self._load_skills()
