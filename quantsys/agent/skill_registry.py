"""Skill registry for Agent."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from loguru import logger


@dataclass
class SkillMeta:
    """Skill metadata from YAML frontmatter."""

    name: str
    description: str
    commands: List[str]
    path: Path
    level1_content: str  # YAML frontmatter + intro


class SkillRegistry:
    """Registry for Agent skills."""

    def __init__(self) -> None:
        """Initialize skill registry."""
        self.skills: Dict[str, SkillMeta] = {}
        self.command_map: Dict[str, str] = {}  # command -> skill_name

    def scan_skills(self, paths: List[Path]) -> None:
        """Scan directories for skills.

        Args:
            paths: List of directories to scan for SKILL.md files
        """
        for base_path in paths:
            if not base_path.exists():
                continue

            for skill_dir in base_path.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        skill = self._parse_skill(skill_file)
                        self.skills[skill.name] = skill

                        # Register commands
                        for cmd in skill.commands:
                            self.command_map[cmd] = skill.name

                    except Exception as e:
                        logger.error(f"Failed to parse skill {skill_file}: {e}")

    def _parse_skill(self, skill_file: Path) -> SkillMeta:
        """Parse a SKILL.md file."""
        content = skill_file.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            raise ValueError("No YAML frontmatter found")

        yaml_content = match.group(1)
        markdown_content = match.group(2)

        # Parse YAML
        metadata = yaml.safe_load(yaml_content)

        return SkillMeta(
            name=metadata.get("name", skill_file.parent.name),
            description=metadata.get("description", ""),
            commands=metadata.get("commands", []),
            path=skill_file.parent,
            level1_content=markdown_content[:2000],  # First 2000 chars for context
        )

    def get_skill(self, name: str) -> Optional[SkillMeta]:
        """Get skill by name."""
        return self.skills.get(name)

    def get_skill_by_command(self, command: str) -> Optional[SkillMeta]:
        """Get skill by command."""
        skill_name = self.command_map.get(command)
        if skill_name:
            return self.skills.get(skill_name)
        return None

    def list_commands(self) -> Dict[str, str]:
        """Get mapping of commands to skill names."""
        return self.command_map.copy()

    def list_skills(self) -> List[SkillMeta]:
        """List all registered skills."""
        return list(self.skills.values())

    def load_full_skill(self, name: str) -> str:
        """Load full skill documentation (Level 2+)."""
        skill = self.skills.get(name)
        if not skill:
            raise ValueError(f"Skill not found: {name}")

        skill_file = skill.path / "SKILL.md"
        return skill_file.read_text(encoding="utf-8")
