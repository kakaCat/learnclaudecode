import re
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills = {}
        if not skills_dir.exists():
            return
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not skill_file.exists():
                continue
            text = skill_file.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", skill_dir.name)
            self.skills[name] = {"meta": meta, "body": body}

    def _parse_frontmatter(self, text: str) -> tuple:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = {}
        current_key = None
        for line in match.group(1).splitlines():
            if re.match(r"^\w[\w-]*\s*:", line):
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip().lstrip("|").strip()
                current_key = key.strip()
            elif current_key and line.startswith("  "):
                meta[current_key] = (meta[current_key] + " " + line.strip()).strip()
        return meta, match.group(2).strip()

    def get_descriptions(self) -> str:
        if not self.skills:
            return "(no skills available)"
        return "\n".join(
            f"  - {name}: {skill['meta'].get('description', 'No description')}"
            for name, skill in self.skills.items()
        )

    def get_content(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills) or 'none'}"
        return f'<skill name="{name}">\n{skill["body"]}\n</skill>'
