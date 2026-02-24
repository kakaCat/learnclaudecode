from backend.app.skill.loader import SkillLoader, SKILLS_DIR

SKILL_LOADER = SkillLoader(SKILLS_DIR)

__all__ = ["SKILL_LOADER", "SkillLoader"]
