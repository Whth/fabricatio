"""Tests for the skill system."""

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_skill.capabilities.skill import UseSkill
from fabricatio_skill.models.skill import get_skill_registry
from fabricatio_skill.rust import Skill, SkillMeta, get_skill, scan_skills, search_skills


class SkillRole(LLMTestRole, UseSkill):
    """Test role that combines LLMTestRole with UseSkill for testing."""


# ── Rust-level tests ─────────────────────────────────────────────────


class TestSkillRust:
    """Tests for Rust-exposed Skill types and functions."""

    def test_skill_creation(self) -> None:
        """Test creating a Skill object directly."""
        skill = Skill(
            name="test",
            description="A test skill",
            tags=["test", "example"],
            content="# Test\nThis is a test skill.",
            path="test.md",
        )
        assert skill.name == "test"
        assert skill.description == "A test skill"
        assert skill.tags == ["test", "example"]
        assert "This is a test skill." in skill.content
        assert skill.path == "test.md"

    def test_skill_meta(self) -> None:
        """Test SkillMeta extraction."""
        skill = Skill(
            name="review",
            description="Code review guidelines",
            tags=["code", "review"],
            content="# Review\nCheck correctness.",
            path="review.md",
        )
        meta = skill.meta()
        assert isinstance(meta, SkillMeta)
        assert meta.name == "review"
        assert meta.description == "Code review guidelines"
        assert meta.tags == ["code", "review"]

    def test_skill_repr(self) -> None:
        """Test Skill repr."""
        skill = Skill(name="test", description="", tags=[], content="x", path="t.md")
        assert "test" in repr(skill)

    def test_scan_skills(self, tmp_path: object) -> None:
        """Test scanning a directory for skill files."""
        from pathlib import Path

        skill_dir = Path(str(tmp_path)) / "skills"
        skill_dir.mkdir()

        (skill_dir / "review.md").write_text(
            "---\nname: code_review\ndescription: Review code\ntags: [code]\n---\n# Review\nCheck quality.",
            encoding="utf-8",
        )
        (skill_dir / "security.md").write_text(
            "---\nname: security\ntags: [security]\n---\n# Security\nCheck vulnerabilities.",
            encoding="utf-8",
        )
        (skill_dir / "plain.md").write_text("# Plain\nJust content.", encoding="utf-8")
        (skill_dir / "notes.txt").write_text("ignored", encoding="utf-8")

        skills = scan_skills(str(skill_dir))
        assert len(skills) == 3

        names = {s.name for s in skills}
        assert "code_review" in names
        assert "security" in names
        assert "plain" in names

    def test_scan_skills_not_found(self) -> None:
        """Test scanning a non-existent directory raises error."""
        with pytest.raises(FileNotFoundError):
            scan_skills("/nonexistent/path")

    def test_search_skills(self) -> None:
        """Test keyword-based skill search."""
        skills = [
            Skill(
                name="code_review",
                description="Review code quality",
                tags=["code", "review"],
                content="Check.",
                path="a.md",
            ),
            Skill(
                name="security", description="Security audit", tags=["security", "audit"], content="Vulns.", path="b.md"
            ),
            Skill(
                name="performance", description="Performance optimization", tags=["perf"], content="Speed.", path="c.md"
            ),
        ]

        results = search_skills("security", skills)
        assert len(results) >= 1
        assert results[0].name == "security"

        results = search_skills("quality", skills)
        assert any(s.name == "code_review" for s in results)

    def test_search_skills_in_content(self) -> None:
        """Test content-level search."""
        skills = [
            Skill(name="a", description="", tags=[], content="SQL injection prevention guide", path="a.md"),
            Skill(name="b", description="", tags=[], content="Performance tuning tips", path="b.md"),
        ]

        results = search_skills("injection", skills, in_content=True)
        assert len(results) == 1
        assert results[0].name == "a"

        results = search_skills("injection", skills, in_content=False)
        assert len(results) == 0

    def test_get_skill(self) -> None:
        """Test exact name lookup."""
        skills = [
            Skill(name="foo", description="", tags=[], content="", path="a.md"),
            Skill(name="bar", description="", tags=[], content="", path="b.md"),
        ]

        assert get_skill("foo", skills) is not None
        assert get_skill("foo", skills).name == "foo"
        assert get_skill("baz", skills) is None


# ── Python-level tests ───────────────────────────────────────────────


class TestUseSkill:
    """Tests for the UseSkill capability mixin."""

    @pytest.fixture(autouse=True)
    def _clear_registry(self) -> None:
        """Ensure the global registry is clean for each test."""
        get_skill_registry().clear()
        yield
        get_skill_registry().clear()

    def test_add_skills(self) -> None:
        """Test adding skills to the role."""
        role = SkillRole()
        skills = [
            Skill(name="a", description="A", tags=[], content="content a", path="a.md"),
            Skill(name="b", description="B", tags=[], content="content b", path="b.md"),
        ]
        role.add_skills(skills)
        assert len(role.skills) == 2

    def test_add_skills_filtered(self) -> None:
        """Test adding skills with name filter."""
        role = SkillRole()
        skills = [
            Skill(name="a", description="A", tags=[], content="content a", path="a.md"),
            Skill(name="b", description="B", tags=[], content="content b", path="b.md"),
        ]
        role.add_skills(skills, names=["a"])
        assert len(role.skills) == 1
        assert role.skills[0].name == "a"

    def test_add_skills_chaining(self) -> None:
        """Test method chaining."""
        role = SkillRole()
        s1 = [Skill(name="a", description="", tags=[], content="", path="a.md")]
        s2 = [Skill(name="b", description="", tags=[], content="", path="b.md")]

        result = role.add_skills(s1).add_skills(s2)
        assert result is role
        assert len(role.skills) == 2

    @pytest.mark.asyncio
    async def test_use_skill_no_skills(self) -> None:
        """Test use_skill with no skills loaded proceeds without context."""
        role = SkillRole()
        role.mock_llm_response("plain answer")

        result = await role.use_skill("What is Python?")
        assert result == "plain answer"

    @pytest.mark.asyncio
    async def test_use_skill_forced_names(self) -> None:
        """Test use_skill with forced skill names and no distill."""
        role = SkillRole()
        role.add_skills(
            [
                Skill(
                    name="review",
                    description="Code review",
                    tags=["code"],
                    content="# Review\nCheck quality.",
                    path="review.md",
                ),
                Skill(
                    name="security",
                    description="Security",
                    tags=["sec"],
                    content="# Security\nCheck vulns.",
                    path="sec.md",
                ),
            ]
        )

        role.mock_llm_response("reviewed answer")

        result = await role.use_skill(
            "Review auth.py",
            names=["review"],
            select=False,
            distill=False,
        )
        assert result == "reviewed answer"
