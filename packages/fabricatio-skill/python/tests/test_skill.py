"""Tests for the skill system."""

from dataclasses import replace

import fabricatio_skill.capabilities.skill as skill_module
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
                name="security",
                description="Security audit",
                tags=["security", "audit"],
                content="Vulns.",
                path="b.md",
            ),
            Skill(
                name="performance",
                description="Performance optimization",
                tags=["perf"],
                content="Speed.",
                path="c.md",
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
        role = SkillRole(name="skill")
        skills = [
            Skill(name="a", description="A", tags=[], content="content a", path="a.md"),
            Skill(name="b", description="B", tags=[], content="content b", path="b.md"),
        ]
        role.add_skills(skills)
        assert len(role.skills) == 2

    def test_add_skills_filtered(self) -> None:
        """Test adding skills with name filter."""
        role = SkillRole(name="skill")
        skills = [
            Skill(name="a", description="A", tags=[], content="content a", path="a.md"),
            Skill(name="b", description="B", tags=[], content="content b", path="b.md"),
        ]
        role.add_skills(skills, names=["a"])
        assert len(role.skills) == 1
        assert role.skills[0].name == "a"

    def test_add_skills_chaining(self) -> None:
        """Test method chaining."""
        role = SkillRole(name="skill")
        s1 = [Skill(name="a", description="", tags=[], content="", path="a.md")]
        s2 = [Skill(name="b", description="", tags=[], content="", path="b.md")]

        result = role.add_skills(s1).add_skills(s2)
        assert result is role
        assert len(role.skills) == 2

    @pytest.mark.asyncio
    async def test_consult_skills_no_skills(self) -> None:
        """Test consult_skills returns empty string when no skills resolve."""
        role = SkillRole(name="skill")
        role.mock_llm_response("plain answer")

        result = await role.consult_skills("What is Python?")
        assert result == ""

    @pytest.mark.asyncio
    async def test_consult_skills_forced_names_raw(self) -> None:
        """Test consult_skills with forced names and no distill returns raw content."""
        role = SkillRole(name="skill")
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
            ],
        )

        result = await role.consult_skills(
            "Review auth.py",
            names=["review"],
            select=False,
            distill=False,
        )
        assert result == "# Review\nCheck quality."

    @pytest.mark.asyncio
    async def test_consult_skills_distills_via_llm(self) -> None:
        """Test consult_skills routes through distill_skills when distill=True."""
        role = SkillRole(name="skill")
        role.add_skills(
            [
                Skill(
                    name="review",
                    description="Code review",
                    tags=["code"],
                    content="# Review\nCheck quality.",
                    path="review.md",
                ),
            ],
        )
        role.mock_llm_response("Check quality.")

        result = await role.consult_skills("Review auth.py", names=["review"])
        assert result == "Check quality."

    @pytest.mark.asyncio
    async def test_consult_skills_llm_select_json_then_distill(self) -> None:
        """Default funnel: validated JSON selection, then distillation (2 calls)."""
        role = SkillRole(name="skill")
        role.add_skills(
            [
                Skill(name="a", description="A", tags=[], content="content a", path="a.md"),
                Skill(name="b", description="B", tags=[], content="content b", path="b.md"),
                Skill(name="c", description="C", tags=[], content="content c", path="c.md"),
            ],
        )
        role.mock_llm_response('["b"]', "essence of b")

        result = await role.consult_skills("Pick b")
        assert result == "essence of b"

    @pytest.mark.asyncio
    async def test_consult_skills_empty_json_means_nothing_relevant(self) -> None:
        """A valid '[]' selection answer skips distillation and yields ''."""
        role = SkillRole(name="skill")
        role.add_skills([Skill(name="a", description="A", tags=[], content="content a", path="a.md")])
        role.mock_llm_response("[]")

        result = await role.consult_skills("Nothing relevant here")
        assert result == ""

    @pytest.mark.asyncio
    async def test_select_skills_tolerates_fenced_json(self) -> None:
        """Selection parses JSON inside a markdown code fence."""
        role = SkillRole(name="skill")
        role.add_skills([Skill(name="a", description="A", tags=[], content="content a", path="a.md")])
        role.mock_llm_response('```json\n["a"]\n```')

        result = await role.consult_skills("Pick a", distill=False)
        assert result == "content a"

    @pytest.mark.asyncio
    async def test_select_skills_drops_unknown_keeps_valid(self) -> None:
        """Unknown names are warned and dropped; valid ones survive."""
        role = SkillRole(name="skill")
        role.add_skills(
            [
                Skill(name="a", description="A", tags=[], content="content a", path="a.md"),
                Skill(name="b", description="B", tags=[], content="content b", path="b.md"),
            ],
        )
        role.mock_llm_response('["a", "ghost"]')

        result = await role.consult_skills("Pick a", distill=False)
        assert result == "content a"

    @pytest.mark.asyncio
    async def test_select_skills_retries_on_garbage_then_succeeds(self) -> None:
        """Non-JSON replies trigger the aask_validate retry loop."""
        role = SkillRole(name="skill")
        role.add_skills([Skill(name="a", description="A", tags=[], content="content a", path="a.md")])
        role.mock_llm_response("comma, list", '["a"]')

        result = await role.consult_skills("Pick a", distill=False)
        assert result == "content a"

    @pytest.mark.asyncio
    async def test_select_skills_capped_by_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Selection never exceeds max_selected_skills (relevance order kept)."""
        role = SkillRole(name="skill")
        role.add_skills(
            [Skill(name=f"s{i}", description=f"d{i}", tags=[], content=f"c{i}", path=f"{i}.md") for i in range(1, 6)],
        )
        monkeypatch.setattr(
            skill_module,
            "skill_config",
            replace(skill_module.skill_config, max_selected_skills=3),
        )
        role.mock_llm_response('["s1", "s2", "s3", "s4", "s5"]')

        result = await role.consult_skills("Pick them all", distill=False)
        assert result == "c1\n\nc2\n\nc3"

    @pytest.mark.asyncio
    async def test_select_skills_keyword_prefilter_excludes_non_matching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Above prefilter_threshold, non-keyword-matching skills leave the pool."""
        role = SkillRole(name="skill")
        role.add_skills(
            [
                Skill(name="kw_alpha", description="alpha docs", tags=[], content="alpha body", path="a.md"),
                Skill(name="kw_beta", description="beta docs", tags=[], content="beta body", path="b.md"),
                Skill(name="no_hit", description="unrelated notes", tags=[], content="unrelated body", path="c.md"),
            ],
        )
        monkeypatch.setattr(
            skill_module,
            "skill_config",
            replace(skill_module.skill_config, prefilter_threshold=2),
        )
        role.mock_llm_response('["kw_alpha", "no_hit"]')

        result = await role.consult_skills("alpha docs", distill=False)
        assert result == "alpha body"

    @pytest.mark.asyncio
    async def test_select_skills_no_prefilter_below_threshold(self, monkeypatch: object, tmp_path: object) -> None:
        """At or below prefilter_threshold, the whole pool reaches the LLM."""
        role = SkillRole(name="skill")
        role.add_skills(
            [
                Skill(name="kw_alpha", description="alpha docs", tags=[], content="alpha body", path="a.md"),
                Skill(name="kw_beta", description="beta docs", tags=[], content="beta body", path="b.md"),
                Skill(name="no_hit", description="unrelated notes", tags=[], content="unrelated body", path="c.md"),
            ],
        )
        monkeypatch.setattr(
            skill_module,
            "skill_config",
            replace(skill_module.skill_config, prefilter_threshold=10),
        )
        role.mock_llm_response('["kw_alpha", "no_hit"]')

        result = await role.consult_skills("alpha docs", distill=False)
        assert result == "alpha body\n\nunrelated body"

    @pytest.mark.asyncio
    async def test_consult_skills_autoloads_default_dirs(self, monkeypatch: object, tmp_path: object) -> None:
        """A role without skills auto-loads default_skill_dirs on first consult."""
        from pathlib import Path

        skill_dir = Path(str(tmp_path)) / "skills"
        skill_dir.mkdir()
        (skill_dir / "one.md").write_text(
            "---\nname: auto_one\ndescription: Auto loaded\ntags: [auto]\n---\n# One\nbody one.",
            encoding="utf-8",
            newline="\n",
        )
        monkeypatch.setattr(
            skill_module,
            "skill_config",
            replace(skill_module.skill_config, default_skill_dirs=[str(skill_dir)]),
        )

        role = SkillRole(name="skill")
        result = await role.consult_skills("anything", select=False, distill=False)

        assert [s.name for s in role.skills] == ["auto_one"]
        assert result == "# One\nbody one."
