"""Tests for the skill system."""

from collections.abc import Iterator
from dataclasses import replace

import fabricatio_skill.capabilities.skill as skill_module
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_skill.capabilities.skill import UseSkill
from fabricatio_skill.config import SkillConfig
from fabricatio_skill.rust import Skill, SkillMeta, SkillRegistry


class SkillRole(LLMTestRole, UseSkill):
    """Test role that combines LLMTestRole with UseSkill for testing."""


@pytest.fixture(autouse=True)
def _clean_library() -> Iterator[None]:
    """Run every test against an empty process-wide library."""
    library = SkillRegistry.instance()
    library.clear()
    yield
    library.clear()


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

    def test_load_scanned_reads_markdown_files(self, tmp_path: object) -> None:
        """Recursive scan parses frontmatter and skips non-markdown files."""
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

        loaded = SkillRegistry.instance().load_scanned([str(skill_dir)])

        assert set(loaded) == {"code_review", "security", "plain"}

    def test_load_scanned_missing_root_raises(self) -> None:
        """A missing root raises and loads nothing."""
        with pytest.raises(FileNotFoundError):
            SkillRegistry.instance().load_scanned(["/nonexistent/path"])

    def test_search_ranks_name_match_first(self) -> None:
        """Keyword search over loaded skills; a name hit outranks a description hit."""
        library = SkillRegistry.instance().add(
            [
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
        )

        results = library.search("security")
        assert results[0].name == "security"

        results = library.search("quality")
        assert any(s.name == "code_review" for s in results)

    def test_search_in_content_gate(self) -> None:
        """``in_content`` decides whether skill bodies are searched."""
        library = SkillRegistry.instance().add(
            [
                Skill(name="a", description="", tags=[], content="SQL injection prevention guide", path="a.md"),
                Skill(name="b", description="", tags=[], content="Performance tuning tips", path="b.md"),
            ]
        )

        results = library.search("injection", in_content=True)
        assert [s.name for s in results] == ["a"]

        assert library.search("injection", in_content=False) == []

    def test_get_by_exact_name(self) -> None:
        """Exact-name lookup; a name that is not loaded resolves to None."""
        library = SkillRegistry.instance().add(
            [
                Skill(name="foo", description="", tags=[], content="", path="a.md"),
                Skill(name="bar", description="", tags=[], content="", path="b.md"),
            ]
        )

        skill = library.get("foo")
        assert skill is not None
        assert skill.name == "foo"
        assert library.get("baz") is None
        assert "bar" in library

    def test_load_by_name_dir_layout(self, tmp_path: object) -> None:
        """Agent-skills convention: <root>/<name>/SKILL.md resolves by name."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        skill_dir = root / "herdr"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            '---\nname: herdr\ndescription: "Terminal mux"\ntags: [cli]\n---\n# Herdr\nbody',
            encoding="utf-8",
            newline="\n",
        )

        registry = SkillRegistry.instance()
        assert registry.load_by_name(["herdr"], [str(root)]) == ["herdr"]

        skill = registry.get("herdr")
        assert skill is not None
        assert skill.name == "herdr"
        assert skill.description == "Terminal mux"
        assert skill.tags == ["cli"]
        assert skill.content == "# Herdr\nbody"
        assert skill.path == "herdr/SKILL.md"

    def test_load_by_name_flat_layout(self, tmp_path: object) -> None:
        """Flat convention: <root>/<name>.md resolves by name."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        root.mkdir()
        (root / "code_review.md").write_text(
            "---\nname: code_review\ndescription: Review code\n---\n# Review\nbody",
            encoding="utf-8",
            newline="\n",
        )

        registry = SkillRegistry.instance()
        assert registry.load_by_name(["code_review"], [str(root)]) == ["code_review"]

        skill = registry.get("code_review")
        assert skill is not None
        assert skill.name == "code_review"
        assert skill.path == "code_review.md"

    def test_load_by_name_dir_layout_wins_over_flat(self, tmp_path: object) -> None:
        """When both conventions exist, <name>/SKILL.md takes precedence."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        (root / "dual").mkdir(parents=True)
        (root / "dual" / "SKILL.md").write_text(
            "---\nname: dual\ndescription: from dir\n---\ndir body",
            encoding="utf-8",
            newline="\n",
        )
        (root / "dual.md").write_text(
            "---\nname: dual\ndescription: from flat\n---\nflat body",
            encoding="utf-8",
            newline="\n",
        )

        registry = SkillRegistry.instance()
        assert registry.load_by_name(["dual"], [str(root)]) == ["dual"]

        skill = registry.get("dual")
        assert skill is not None
        assert skill.description == "from dir"

    def test_load_by_name_skips_missing_name(self, tmp_path: object) -> None:
        """A name no root resolves is skipped instead of raising."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        root.mkdir()

        assert SkillRegistry.instance().load_by_name(["nope"], [str(root)]) == []

    def test_load_by_name_rejects_path_like_names(self, tmp_path: object) -> None:
        """Separators, dot components, and empty names are rejected."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        root.mkdir()

        assert SkillRegistry.instance().load_by_name(["", ".", "..", "a/b", "a\\b", "../../evil"], [str(root)]) == []

    def test_library_keeps_one_copy_until_removed(self, tmp_path: object) -> None:
        """A loaded skill is not re-read while it stays in the library; remove() frees it."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        root.mkdir()
        skill_file = root / "cached.md"
        skill_file.write_text(
            "---\nname: cached\ndescription: first\n---\nbody",
            encoding="utf-8",
            newline="\n",
        )

        library = SkillRegistry.instance()
        assert library.load_scanned([str(root)]) == ["cached"]
        first = library.get("cached")
        assert first is not None
        assert first.description == "first"

        # The file changes on disk, but the library keeps the copy it already parsed -
        # and still reports the name as available.
        skill_file.write_text(
            "---\nname: cached\ndescription: second\n---\nbody",
            encoding="utf-8",
            newline="\n",
        )
        assert library.load_scanned([str(root)]) == ["cached"]
        still_first = library.get("cached")
        assert still_first is not None
        assert still_first.description == "first"

        # remove() drops the copy, so the next load reads the file again.
        assert library.remove(["cached"]).load_scanned([str(root)]) == ["cached"]
        reloaded = library.get("cached")
        assert reloaded is not None
        assert reloaded.description == "second"


# ── Python-level tests ───────────────────────────────────────────────


class TestUseSkill:
    """Tests for the UseSkill capability mixin."""

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

    def test_library_is_shared_across_roles(self) -> None:
        """A skill loaded through one role is visible to every other role."""
        loader = SkillRole(name="loader")
        loader.add_skills([Skill(name="shared", description="S", tags=[], content="shared body", path="s.md")])

        reader = SkillRole(name="reader", skill_names=["shared"])

        assert "shared" in reader.skill_library
        assert [s.content for s in reader.skills] == ["shared body"]

    def test_scan_skills_tracks_new_names_and_chains(self, tmp_path: object) -> None:
        """The role loader scans a tree, tracks what it loaded, chains, and is idempotent."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "team"
        (root / "one").mkdir(parents=True)
        (root / "one" / "SKILL.md").write_text(
            "---\nname: one\ndescription: One\n---\nbody one",
            encoding="utf-8",
            newline="\n",
        )
        (root / "two.md").write_text(
            "---\nname: two\ndescription: Two\n---\nbody two",
            encoding="utf-8",
            newline="\n",
        )

        role = SkillRole(name="skill")
        assert role.scan_skills(root) is role
        assert role.skill_names == ["one", "two"]
        assert [s.name for s in role.skills] == ["one", "two"]

        # Idempotent: scanning again adds no duplicate names.
        role.scan_skills(root)
        assert role.skill_names == ["one", "two"]

    def test_gather_skills_by_name(self, tmp_path: object) -> None:
        """Gather both layouts by name: registered, tracked in order, chained; missing skipped."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        (root / "dir_skill").mkdir(parents=True)
        (root / "dir_skill" / "SKILL.md").write_text(
            "---\nname: dir_skill\ndescription: D\n---\n# Dir\nbody dir.",
            encoding="utf-8",
            newline="\n",
        )
        (root / "flat_skill.md").write_text(
            "---\nname: flat_skill\ndescription: F\n---\n# Flat\nbody flat.",
            encoding="utf-8",
            newline="\n",
        )

        role = SkillRole(name="skill")
        result = role.gather_skills(["dir_skill", "nope", "flat_skill"], dirs=[str(root)])

        assert result is role
        assert role.skill_names == ["dir_skill", "flat_skill"]
        assert "dir_skill" in role.skill_library
        assert "flat_skill" in role.skill_library

        # Duplicate names collapse to a single library entry.
        deduped = SkillRegistry.instance().clear().load_by_name(["dir_skill", "dir_skill"], [str(root)])
        assert deduped == ["dir_skill"]

    def test_gather_skills_first_root_wins(self, tmp_path: object) -> None:
        """The first lookup root that resolves a name supplies the skill."""
        from pathlib import Path

        root_a = Path(str(tmp_path)) / "a"
        root_b = Path(str(tmp_path)) / "b"
        for root, desc in ((root_a, "from a"), (root_b, "from b")):
            (root / "dual").mkdir(parents=True)
            (root / "dual" / "SKILL.md").write_text(
                f"---\nname: dual\ndescription: {desc}\n---\nbody",
                encoding="utf-8",
                newline="\n",
            )

        library = SkillRegistry.instance()
        assert library.load_by_name(["dual"], [str(root_a), str(root_b)]) == ["dual"]
        first = library.get("dual")
        assert first is not None
        assert first.description == "from a"

        # The library holds one copy per name, so re-resolve from an empty library.
        assert library.clear().load_by_name(["dual"], [str(root_b), str(root_a)]) == ["dual"]
        second = library.get("dual")
        assert second is not None
        assert second.description == "from b"

    @pytest.mark.asyncio
    async def test_gather_skills_feeds_consult(self, tmp_path: object) -> None:
        """A gathered skill is consultable through the normal pipeline."""
        from pathlib import Path

        root = Path(str(tmp_path)) / "lib"
        (root / "gathered").mkdir(parents=True)
        (root / "gathered" / "SKILL.md").write_text(
            "---\nname: gathered\ndescription: G\n---\n# Gathered\nreal body.",
            encoding="utf-8",
            newline="\n",
        )

        role = SkillRole(name="skill")
        role.gather_skills(["gathered"], dirs=[str(root)])

        result = await role.consult_skills("q", names=["gathered"], select=False, distill=False)
        assert result == "# Gathered\nreal body."

    def test_gather_skills_expands_default_dirs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        """dirs=None reads default_skill_dirs and expands `~` against the user home."""
        from pathlib import Path
        from unittest.mock import patch

        home = Path(str(tmp_path)) / "home"
        skill_dir = home / ".agents" / "skills" / "tilde_one"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: tilde_one\ndescription: T\n---\nbody",
            encoding="utf-8",
            newline="\n",
        )
        monkeypatch.setenv("USERPROFILE", str(home))
        monkeypatch.setenv("HOME", str(home))

        role = SkillRole(name="skill")
        with patch.object(
            skill_module,
            "skill_config",
            replace(skill_module.skill_config, default_skill_dirs=["~/.agents/skills"]),
        ):
            role.gather_skills(["tilde_one"])

        assert [s.name for s in role.skills] == ["tilde_one"]

    def test_default_dirs_include_agents_skills(self) -> None:
        """The declared default lookup roots include the user-level agent-skills library."""
        assert "~/.agents/skills" in SkillConfig().default_skill_dirs

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

    @pytest.mark.asyncio
    async def test_select_skills_k_overrides_cap(self) -> None:
        """k=None falls back to the config cap; k>0 trims; k=0 keeps everything above the cap."""
        role = SkillRole(name="skill")
        role.add_skills(
            [Skill(name=f"s{i}", description=f"D{i}", tags=[], content=f"c{i}", path=f"{i}.md") for i in range(1, 6)]
        )
        role.mock_llm_response('["s1", "s2", "s3", "s4", "s5"]')

        capped = await role.select_skills("pick", k=2)
        assert capped is not None
        assert [s.name for s in capped] == ["s1", "s2"]

        role.mock_llm_response('["s1", "s2", "s3", "s4", "s5"]')
        unlimited = await role.select_skills("pick", k=0)
        assert unlimited is not None
        assert [s.name for s in unlimited] == ["s1", "s2", "s3", "s4", "s5"]

        role.mock_llm_response('["s1", "s2", "s3", "s4", "s5"]')
        config_cap = await role.select_skills("pick")
        assert config_cap is not None
        assert len(config_cap) == 5
