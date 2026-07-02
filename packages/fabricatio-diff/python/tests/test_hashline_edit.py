"""Integration tests for `fabricatio_diff.capabilities.hashline_edit.HashlineEdit`.

Three test classes:
  1. `TestHashlineEditProgrammatic` — 7 async wrapper methods; no LLM involved.
  2. `TestParseHashlineDiffResponse` — parser unit tests for various LLM response shapes.
  3. `TestHashlineDiffLoop` — full LLM loop with mock LLM, stub templates,
     exercising the error-feedback re-prompt and exhausted-iteration paths.
"""

import dataclasses
from pathlib import Path

import pytest
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_diff.capabilities.hashline_edit import (
    HashlineDiffResult,
    HashlineEdit,
    HashlineEditExhaustedError,
    HashlineOp,
)
from fabricatio_diff.config import diff_config
from fabricatio_diff.rust import (
    apply_insert_after,
    apply_replace,
    apply_replace_lines,
    apply_set_line,
    compute_hash,
    format_hashes,
    parse_hashline_anchor,
)
from fabricatio_diff.utils import HashlineDelimiters
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.utils import code_block, install_router_usage

# ─── Stub templates ───────────────────────────────────────────────────────
# Real `built-in/hashline_diff` and `built-in/hashline_judge` are loaded from
# a template_stores directory at runtime. In tests we install local stubs and
# override the config to point at them, so we don't need to ship the .hbs
# files or pollute the global config.

_STUB_HASHLINE_DIFF_TEMPLATE = """\
SOURCE:
{{source}}
REQUIREMENT: {{requirement}}
LAST_ERROR: {{last_error}}
"""

_STUB_HASHLINE_JUDGE_TEMPLATE = """\
REQUIREMENT: {{requirement}}
CONTENT:
{{content}}
"""


@pytest.fixture
def stub_hashline_templates(tmp_path: Path) -> tuple[str, str]:
    """Install stub .hbs templates and return their discoverable names.

    Returns:
        A tuple of (diff_template_name, judge_template_name).
    """
    test_dir = tmp_path / "templates"
    test_dir.mkdir()
    (test_dir / "test_hashline_diff.hbs").write_text(_STUB_HASHLINE_DIFF_TEMPLATE)
    (test_dir / "test_hashline_judge.hbs").write_text(_STUB_HASHLINE_JUDGE_TEMPLATE)

    TEMPLATE_MANAGER.add_store(test_dir, rediscovery=True)

    # Handlebars uses the filename (without .hbs) as the template name.
    return "test_hashline_diff", "test_hashline_judge"


@pytest.fixture
def with_stub_templates(stub_hashline_templates: tuple[str, str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """Install stub templates AND patch the config to reference them.

    `DiffConfig` is frozen, so we build a new instance via `dataclasses.replace`
    and swap the module-level binding in `fabricatio_diff.capabilities.hashline_edit`
    for the duration of the test. The `monkeypatch` undoes the swap on teardown.
    """
    from fabricatio_diff.capabilities import hashline_edit as he_mod

    diff_name, judge_name = stub_hashline_templates
    new_cfg = dataclasses.replace(
        diff_config,
        hashline_diff_template=diff_name,
        hashline_judge_template=judge_name,
        hashline_diff_max_iterations=3,
    )
    monkeypatch.setattr(he_mod, "diff_config", new_cfg)
    return diff_name, judge_name


# ─── Test role ────────────────────────────────────────────────────────────


class HashlineEditRole(LLMTestRole, HashlineEdit):
    """Test role combining the LLMTestRole base with HashlineEdit."""


@pytest.fixture
def role() -> HashlineEditRole:
    """Build a fresh `HashlineEditRole` for each test."""
    return HashlineEditRole()


# ─── 1. Programmatic wrappers ─────────────────────────────────────────────


class TestHashlineEditProgrammatic:
    """Tests for the 7 async wrappers over the Rust hashline primitives.

    These do not go through the LLM. The async wrapper is just a thin shell;
    the underlying behavior is in the Rust crate, already covered by
    `test_hashline.py`. Here we verify the wrapper signatures and that
    errors propagate as `RuntimeError` (from the Rust PyRuntimeError mapping).
    """

    @pytest.mark.asyncio
    async def test_compute_line_hash(self, role: HashlineEditRole) -> None:
        """Wrapper returns the same value as the raw Rust binding."""
        assert await role.compute_line_hash("hello") == compute_hash("hello")
        # Whitespace-stripped: leading/trailing ignored.
        assert await role.compute_line_hash("  hello  ") == compute_hash("hello")

    @pytest.mark.asyncio
    async def test_format_hashes(self, role: HashlineEditRole) -> None:
        """Wrapper returns the same value as the raw Rust binding."""
        result = await role.format_hashes("a\nb\nc", start_line=10)
        assert result == format_hashes("a\nb\nc", 10)

    @pytest.mark.asyncio
    async def test_parse_anchor(self, role: HashlineEditRole) -> None:
        """Wrapper accepts display suffixes and whitespace around the colon."""
        assert await role.parse_anchor("5:a3") == (5, "a3")
        assert await role.parse_anchor("5:a3|some content") == (5, "a3")
        assert await role.parse_anchor("5 : a3") == (5, "a3")
        assert await role.parse_anchor("5:a3") == parse_hashline_anchor("5:a3")

    @pytest.mark.asyncio
    async def test_set_line(self, role: HashlineEditRole) -> None:
        """Wrapper applies the edit and matches the raw Rust binding."""
        content = "line1\nline2\nline3"
        anchor = format_hashes(content).split("\n")[1].split("|")[0]
        out = await role.set_line(content, anchor, "REPLACED")
        assert out == "line1\nREPLACED\nline3"
        assert out == apply_set_line(content, anchor, "REPLACED")

    @pytest.mark.asyncio
    async def test_insert_after_rejects_empty_text(self, role: HashlineEditRole) -> None:
        """Empty text raises ValueError before the Rust call."""
        with pytest.raises(ValueError, match="non-empty"):
            await role.insert_after("line1\nline2", "1:xx", "")

    @pytest.mark.asyncio
    async def test_insert_after_happy(self, role: HashlineEditRole) -> None:
        """Wrapper applies the insert and matches the raw Rust binding."""
        content = "line1\nline2"
        anchor = format_hashes(content).split("\n")[0].split("|")[0]
        out = await role.insert_after(content, anchor, "# inserted")
        assert out == "line1\n# inserted\nline2"
        assert out == apply_insert_after(content, anchor, "# inserted")

    @pytest.mark.asyncio
    async def test_replace_lines_happy(self, role: HashlineEditRole) -> None:
        """Wrapper applies the range replace and matches the raw Rust binding."""
        content = "line1\nline2\nline3\nline4"
        formatted = format_hashes(content).split("\n")
        start = formatted[1].split("|")[0]
        end = formatted[2].split("|")[0]
        out = await role.replace_lines(content, start, end, "REPLACED")
        assert out == "line1\nREPLACED\nline4"
        assert out == apply_replace_lines(content, start, end, "REPLACED")

    @pytest.mark.asyncio
    async def test_replace_happy(self, role: HashlineEditRole) -> None:
        """Wrapper applies the fuzzy replace and matches the raw Rust binding."""
        out = await role.replace("hello world", "world", "earth")
        assert out == "hello earth"
        assert out == apply_replace("hello world", "world", "earth", False)

    @pytest.mark.asyncio
    async def test_replace_text_not_found_raises(self, role: HashlineEditRole) -> None:
        """The Rust `apply_replace` raises `PyRuntimeError` on TextNotFound."""
        with pytest.raises(RuntimeError, match="Text not found"):
            await role.replace("hello world", "missing", "x")

    @pytest.mark.asyncio
    async def test_max_iterations_validation(self, role: HashlineEditRole) -> None:
        """`max_iterations < 1` raises ValueError before any LLM call."""
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            await role.hashline_diff("source", "req", max_iterations=0)


# ─── 2. Parser unit tests ─────────────────────────────────────────────────


class TestParseHashlineDiffResponse:
    """Unit tests for `_parse_hashline_diff_response` covering various LLM shapes."""

    def _parse(self, role: HashlineEditRole, resp: str) -> list[HashlineOp] | None:
        return role._parse_hashline_diff_response(resp)

    def test_single_set_line(self, role: HashlineEditRole) -> None:
        """A single `<<<<SET` block parses to one set_line op."""
        resp = f"{HashlineDelimiters.SET_LEFT.value} 2:b2\nNEW\n{HashlineDelimiters.SET_RIGHT.value}"
        edits = self._parse(role, resp)
        assert edits is not None
        assert len(edits) == 1
        assert edits[0] == HashlineOp(kind="set_line", anchor="2:b2", new_text="NEW")

    def test_single_replace_lines(self, role: HashlineEditRole) -> None:
        """A single `<<<<RANGE` block parses to one replace_lines op."""
        resp = f"{HashlineDelimiters.RANGE_LEFT.value} 3:83 4:5f\na\nb\n{HashlineDelimiters.RANGE_RIGHT.value}"
        edits = self._parse(role, resp)
        assert edits is not None
        assert len(edits) == 1
        assert edits[0].kind == "replace_lines"
        assert edits[0].start_anchor == "3:83"
        assert edits[0].end_anchor == "4:5f"
        assert edits[0].new_text == "a\nb"

    def test_insert_after_non_empty(self, role: HashlineEditRole) -> None:
        """A non-empty `<<<<INSERT_AFTER` block parses successfully."""
        resp = f"{HashlineDelimiters.INSERT_LEFT.value} 1:02\n# c\n{HashlineDelimiters.INSERT_RIGHT.value}"
        edits = self._parse(role, resp)
        assert edits is not None
        assert edits[0].kind == "insert_after"
        assert edits[0].anchor == "1:02"
        assert edits[0].text == "# c"

    def test_insert_after_empty_text_rejected(self, role: HashlineEditRole) -> None:
        """An INSERT_AFTER block with empty text is rejected (returns None)."""
        resp = f"{HashlineDelimiters.INSERT_LEFT.value} 1:02\n{HashlineDelimiters.INSERT_RIGHT.value}"
        assert self._parse(role, resp) is None

    def test_replace_basic(self, role: HashlineEditRole) -> None:
        """A `<<<<REPLACE` block without `ALL` parses with all=False."""
        resp = f"{HashlineDelimiters.REPLACE_LEFT.value}\nold\nnew\n{HashlineDelimiters.REPLACE_RIGHT.value}"
        edits = self._parse(role, resp)
        assert edits is not None
        assert edits[0].kind == "replace"
        assert edits[0].old_text == "old"
        assert edits[0].new_text == "new"
        assert edits[0].all is False

    def test_replace_all(self, role: HashlineEditRole) -> None:
        """A `<<<<REPLACE ALL` block parses with all=True."""
        resp = f"{HashlineDelimiters.REPLACE_LEFT.value} ALL\nfoo\nbar\n{HashlineDelimiters.REPLACE_RIGHT.value}"
        edits = self._parse(role, resp)
        assert edits is not None
        assert edits[0].kind == "replace"
        assert edits[0].all is True
        assert edits[0].old_text == "foo"
        assert edits[0].new_text == "bar"

    def test_mixed_kinds_preserve_document_order(self, role: HashlineEditRole) -> None:
        """Three different op kinds in one response come out in source order."""
        resp = (
            f"{HashlineDelimiters.SET_LEFT.value} 2:b2\nA\n{HashlineDelimiters.SET_RIGHT.value}\n"
            f"{HashlineDelimiters.INSERT_LEFT.value} 1:02\nB\n{HashlineDelimiters.INSERT_RIGHT.value}\n"
            f"{HashlineDelimiters.SET_LEFT.value} 3:83\nC\n{HashlineDelimiters.SET_RIGHT.value}"
        )
        edits = self._parse(role, resp)
        assert edits is not None
        assert [e.kind for e in edits] == ["set_line", "insert_after", "set_line"]
        assert [e.anchor for e in edits] == ["2:b2", "1:02", "3:83"]

    def test_tolerates_preamble_and_postamble(self, role: HashlineEditRole) -> None:
        """Preamble/postamble text around the block is silently ignored."""
        resp = (
            "Here are the edits:\n\n"
            f"{HashlineDelimiters.SET_LEFT.value} 2:b2\nNEW\n{HashlineDelimiters.SET_RIGHT.value}\n\n"
            "Done!"
        )
        edits = self._parse(role, resp)
        assert edits is not None
        assert len(edits) == 1
        assert edits[0].new_text == "NEW"

    def test_unclosed_block_returns_none(self, role: HashlineEditRole) -> None:
        """A block without a closer returns None (caller re-prompts)."""
        resp = f"{HashlineDelimiters.SET_LEFT.value} 2:b2\nNEW"
        assert self._parse(role, resp) is None

    def test_no_blocks_returns_none(self, role: HashlineEditRole) -> None:
        """Preamble-only text returns None."""
        assert self._parse(role, "I have no edits to suggest.") is None

    def test_malformed_anchor_returns_none(self, role: HashlineEditRole) -> None:
        """A block whose anchor doesn't parse as `LINE:HASH` returns None.

        `parse_hashline_anchor` raises `RuntimeError` on invalid format; the
        parser must catch that and return None instead of letting the
        exception bubble out of the LLM loop.
        """
        resp = f"{HashlineDelimiters.SET_LEFT.value} not-an-anchor\nNEW\n{HashlineDelimiters.SET_RIGHT.value}"
        assert self._parse(role, resp) is None


# ─── 3. LLM-driven loop with mock ────────────────────────────────────────


class TestHashlineDiffLoop:
    """End-to-end tests for the self-correcting LLM loop, using `fabricatio_mock`.

    NOTE: The Rust `ajudge` parses responses via `capture_json_codeblock` (a
    ```json``` fence) and `serde_json::from_str::<bool>`, so judge responses
    must be JSON-encoded booleans wrapped in a fence. The mock's LIFO
    reversal means the WHOLE passed list is FIFO-ordered — so LLM responses
    and judge responses must be interleaved explicitly. Use `code_block()`
    to build individual judge responses and avoid the `padding=10` default
    of `return_json_router_usage` (which makes every call after the first
    return the same value).
    """

    @pytest.mark.asyncio
    async def test_satisfied_on_first_try(
        self,
        role: HashlineEditRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """LLM emits a valid edit, judge says YES → loop returns satisfied."""
        source = "line1\nline2\nline3"
        anchor_2 = format_hashes(source).split("\n")[1].split("|")[0]
        llm_response = f"{HashlineDelimiters.SET_LEFT.value} {anchor_2}\nNEW_LINE\n{HashlineDelimiters.SET_RIGHT.value}"
        with install_router_usage(llm_response, code_block("true", "json")):
            result = await role.hashline_diff(source, "rename line2 to NEW_LINE")

        assert isinstance(result, HashlineDiffResult)
        assert result.satisfied is True
        assert result.iterations == 1
        assert result.content == "line1\nNEW_LINE\nline3"
        assert len(result.applied_edits) == 1
        assert result.applied_edits[0].kind == "set_line"

    @pytest.mark.asyncio
    async def test_recovers_from_apply_mismatch(
        self,
        role: HashlineEditRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """Recover from an out-of-bounds anchor (iter 1) and a rejected apply (iter 2).

        Iter 1: anchor 99:99 is OOB (only 3 lines), apply raises; no judge.
        Iter 2: anchor 2:b2 is valid for the original source, apply succeeds,
                judge says NO (mocked false). The apply changed line 2 -> "FIXED".
        Iter 3: anchor must match the post-iter-2 state. We pre-compute the
                new hash for line "FIXED" and emit a corrected edit. Judge YES.
        """
        source = "line1\nline2\nline3"
        bad_resp = f"{HashlineDelimiters.SET_LEFT.value} 99:99\nWHATEVER\n{HashlineDelimiters.SET_RIGHT.value}"
        # Anchor for the original source line 2.
        anchor_2_orig = format_hashes(source).split("\n")[1].split("|")[0]
        # After iter 2 applies, line 2 becomes "FIXED" -> its hash changes.
        post_iter_2 = "line1\nFIXED\nline3"
        anchor_2_new = format_hashes(post_iter_2).split("\n")[1].split("|")[0]
        good_resp_v1 = (
            f"{HashlineDelimiters.SET_LEFT.value} {anchor_2_orig}\nFIXED\n{HashlineDelimiters.SET_RIGHT.value}"
        )
        good_resp_v2 = (
            f"{HashlineDelimiters.SET_LEFT.value} {anchor_2_new}\nREPLACED\n{HashlineDelimiters.SET_RIGHT.value}"
        )
        # Sequence (interleaved LLM responses and judge calls in one FIFO queue):
        #   iter 1: aask -> bad_resp; apply raises (OOB); continue (no judge)
        #   iter 2: aask -> good_resp_v1; apply succeeds; ajudge -> "false"
        #   iter 3: aask -> good_resp_v2; apply succeeds; ajudge -> "true"
        mock_sequence = (
            bad_resp,
            good_resp_v1,
            code_block("false", "json"),
            good_resp_v2,
            code_block("true", "json"),
            code_block("true", "json"),  # padding
        )
        with install_router_usage(*mock_sequence):
            result = await role.hashline_diff(source, "rename line2")

        assert result.satisfied is True
        # 3 aask calls total: iter 1 (apply OOB), iter 2 (apply ok, judge NO),
        # iter 3 (apply ok, judge YES).
        assert result.iterations == 3
        assert result.content == "line1\nREPLACED\nline3"
        # history should have a "judge NO" breadcrumb from iter 2.
        assert any("judge NO" in h for h in result.history)

    @pytest.mark.asyncio
    async def test_recovers_from_parse_failure(
        self,
        role: HashlineEditRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """First attempt: malformed response (parse fail). Second: valid response + judge YES."""
        source = "line1\nline2"
        anchor_2 = format_hashes(source).split("\n")[1].split("|")[0]
        good_resp = f"{HashlineDelimiters.SET_LEFT.value} {anchor_2}\nOK\n{HashlineDelimiters.SET_RIGHT.value}"
        # First LLM call returns garbage (parse fail, no judge).
        # Second LLM call returns a valid edit, judge says "true".
        with install_router_usage(
            "I'm not sure how to do that.",
            good_resp,
            code_block("true", "json"),
            code_block("true", "json"),
        ):
            result = await role.hashline_diff(source, "rename line2")

        assert result.satisfied is True
        # Parse failure doesn't increment llm_calls; only successful `aask` calls count.
        assert result.iterations == 2
        assert "parse failure" in result.history
        assert result.content == "line1\nOK"

    @pytest.mark.asyncio
    async def test_exhausts_iterations(
        self,
        role: HashlineEditRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """Judge keeps saying NO → loop exhausts max_iterations and raises."""
        source = "line1\nline2"
        anchor_2 = format_hashes(source).split("\n")[1].split("|")[0]
        resp = f"{HashlineDelimiters.SET_LEFT.value} {anchor_2}\nX\n{HashlineDelimiters.SET_RIGHT.value}"
        # 3 LLM calls, each followed by a judge "false"; max_iterations=3.
        mock_sequence = (
            resp,
            code_block("false", "json"),
            resp,
            code_block("false", "json"),
            resp,
            code_block("false", "json"),
            code_block("false", "json"),  # padding
        )
        with install_router_usage(*mock_sequence), pytest.raises(HashlineEditExhaustedError) as exc_info:
            await role.hashline_diff(source, "any requirement")

        err = exc_info.value
        assert err.iterations == 3
        assert err.last_source == "line1\nX"
