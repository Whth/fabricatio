"""Capability for line-anchored, hashline-driven text editing.

Combines a set of programmatic wrappers over the Rust hashline primitives with
an LLM-driven self-correcting loop that iteratively applies edits until a
natural-language requirement is satisfied.
"""

from abc import ABC
from dataclasses import dataclass, field
from typing import Literal

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.usages import UseLLM

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
from fabricatio_diff.utils import (
    HashlineDelimiters,
    HashlineInsertAfterCapture,
    HashlineRangeCapture,
    HashlineReplaceCapture,
    HashlineSetCapture,
)


@dataclass(frozen=True)
class HashlineOp:
    """A single hashline edit op parsed from an LLM response.

    Mirrors the rho-hashline `HashlineEdit` shape 1:1. The four kinds map
    directly to the four Rust primitives exposed via `fabricatio_diff.rust`.
    """

    kind: Literal["set_line", "replace_lines", "insert_after", "replace"]
    """Op kind; selects which field is meaningful."""

    anchor: str | None = None
    """`LINE:HASH` for `set_line` / `insert_after`."""
    start_anchor: str | None = None
    """`LINE:HASH` for the range start (`replace_lines`)."""
    end_anchor: str | None = None
    """`LINE:HASH` for the range end (`replace_lines`)."""
    new_text: str | None = None
    """Replacement content for `set_line` / `replace_lines` / `replace`."""
    text: str | None = None
    """Inserted content for `insert_after`."""
    old_text: str | None = None
    """Match content for `replace`."""
    all: bool = False
    """If True, replace all occurrences (`replace`)."""


@dataclass(frozen=True)
class HashlineDiffResult:
    """Outcome of a `hashline_diff` loop run."""

    content: str
    """Final source after all applied edits."""
    applied_edits: list[HashlineOp] = field(default_factory=list)
    """All ops applied across iterations, in order."""
    iterations: int = 0
    """Number of LLM calls actually made (parse-only iterations are not counted)."""
    satisfied: bool = False
    """Whether the final judge verdict was YES."""
    history: list[str] = field(default_factory=list)
    """Per-iteration debug breadcrumbs (parse failures, judge verdicts, etc.)."""


class HashlineEditExhaustedError(RuntimeError):
    """Raised when `hashline_diff` cannot reach a satisfied state in time.

    Attributes:
        iterations: Number of LLM calls made before giving up.
        last_source: Content after the last successful apply.
        last_error: Error from the last failed apply, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        iterations: int,
        last_source: str,
        last_error: str | None,
    ) -> None:
        """Store the failure context for post-mortem inspection.

        Args:
            message: Human-readable description of why the loop gave up.
            iterations: Number of LLM calls made before giving up.
            last_source: Content after the last successful apply.
            last_error: Error from the last failed apply, if any.
        """
        super().__init__(message)
        self.iterations = iterations
        self.last_source = last_source
        self.last_error = last_error


class HashlineEdit(UseLLM, ABC):
    """Line-anchored editing via hashlines.

    Provides thin wrappers over the Rust hashline primitives for programmatic
    use, and a self-correcting LLM loop (`hashline_diff`) that iteratively
    applies edits until a natural-language requirement is satisfied.
    """

    # ─── Programmatic wrappers ──────────────────────────────────────────

    async def compute_line_hash(self, line: str) -> str:
        """Compute the 2-char hex hash of a single line.

        Whitespace is stripped before hashing, so `"  foo  "` and `"foo"` hash equal.
        """
        return compute_hash(line)

    async def format_hashes(self, content: str, start_line: int = 1) -> str:
        r"""Format `content` as `LINE:HASH|content` per line, `\n`-joined.

        The HASH is the 2-char hex hash of the line (whitespace-stripped).
        """
        return format_hashes(content, start_line)

    async def parse_anchor(self, anchor: str) -> tuple[int, str]:
        """Parse a `LINE:HASH` anchor into `(line_number, hash)`.

        Accepts display suffixes (`5:a3|some content`) and whitespace around
        the colon.
        """
        return parse_hashline_anchor(anchor)

    async def set_line(self, content: str, anchor: str, new_text: str) -> str:
        """Replace the line at `anchor` with `new_text`.

        `anchor` is a `LINE:HASH` string. `new_text` may span multiple lines.

        Raises:
            RuntimeError: On `HashlineError` (InvalidAnchor, Mismatch, etc.).
        """
        return apply_set_line(content, anchor, new_text)

    async def insert_after(self, content: str, anchor: str, text: str) -> str:
        """Insert `text` after the line at `anchor`.

        `text` must be non-empty (validated before the Rust call to surface
        the LLM's likely mistake as a clearer error).

        Raises:
            ValueError: If `text` is empty.
            RuntimeError: On any `HashlineError`.
        """
        if not text:
            raise ValueError("insert_after requires non-empty `text`")
        return apply_insert_after(content, anchor, text)

    async def replace_lines(self, content: str, start_anchor: str, end_anchor: str, new_text: str) -> str:
        """Replace the inclusive line range `[start_anchor, end_anchor]` with `new_text`.

        Collapses to a single-line replace when `start_anchor` and `end_anchor`
        resolve to the same line.

        Raises:
            RuntimeError: On any `HashlineError`.
        """
        return apply_replace_lines(content, start_anchor, end_anchor, new_text)

    async def replace(self, content: str, old_text: str, new_text: str, all: bool = False) -> str:
        """Fuzzy text substitution (whitespace-insensitive).

        If `all` is False (default), `old_text` must match exactly once or the
        call raises `MultipleMatches`. If `all` is True, all occurrences are
        replaced.

        Raises:
            RuntimeError: On `TextNotFound` or `MultipleMatches`.
        """
        return apply_replace(content, old_text, new_text, all)

    # ─── LLM-driven self-correcting loop ────────────────────────────────

    async def hashline_diff(
        self,
        source: str,
        requirement: str,
        *,
        max_iterations: int | None = None,
    ) -> HashlineDiffResult:
        """Iteratively apply hashline edits until `requirement` is satisfied.

        Each iteration:
          1. Render `hashline_diff_template` with `{source, requirement, last_error}`.
          2. Parse the LLM response into a list of `HashlineOp`s.
          3. Apply via Rust. On `HashlineError` (Mismatch / LineOutOfBounds /
             InvalidAnchor), capture the error message and re-prompt.
          4. Call `ajudge` with `hashline_judge_template`. If YES, return.
             If NO, loop.

        Args:
            source: The current text to edit.
            requirement: Natural-language description of the target state.
            max_iterations: Override for `diff_config.hashline_diff_max_iterations`.

        Returns:
            A `HashlineDiffResult` describing the final state.

        Raises:
            HashlineEditExhaustedError: When the loop cannot satisfy
                `requirement` within `max_iterations` iterations.
        """
        max_iter = max_iterations if max_iterations is not None else diff_config.hashline_diff_max_iterations
        if max_iter < 1:
            raise ValueError("max_iterations must be >= 1")

        history: list[str] = []
        applied: list[HashlineOp] = []
        current = source
        last_error: str | None = None
        llm_calls = 0

        for _ in range(1, max_iter + 1):
            # 1. Build prompt
            prompt = TEMPLATE_MANAGER.render_template(
                diff_config.hashline_diff_template,
                {
                    "source": format_hashes(current),
                    "requirement": requirement,
                    "last_error": last_error or "(none — this is your first attempt)",
                },
            )

            # 2. Get + parse response
            resp = await self.aask(prompt)
            llm_calls += 1
            edits = self._parse_hashline_diff_response(resp)
            if edits is None:
                last_error = (
                    "Failed to parse your response. Re-emit using the per-op "
                    "block delimiters "
                    f"(`{HashlineDelimiters.SET_LEFT.value} <anchor>`, "
                    f"`{HashlineDelimiters.RANGE_LEFT.value} <start> <end>`, "
                    f"`{HashlineDelimiters.INSERT_LEFT.value} <anchor>`, "
                    f"`{HashlineDelimiters.REPLACE_LEFT.value}`)."
                )
                history.append("parse failure")
                continue

            # 3. Apply
            try:
                current = self._apply_edits(current, edits)
                applied.extend(edits)
                last_error = None
            except RuntimeError as e:
                last_error = f"Apply failed: {e}"
                history.append(f"apply error (truncated): {str(e)[:200]}")
                continue

            # 4. Judge
            judge_prompt = TEMPLATE_MANAGER.render_template(
                diff_config.hashline_judge_template,
                {"requirement": requirement, "content": current},
            )
            verdict = await self.ajudge(judge_prompt)
            if verdict:
                history.append(f"judge YES after {llm_calls} LLM call(s)")
                return HashlineDiffResult(
                    content=current,
                    applied_edits=applied,
                    iterations=llm_calls,
                    satisfied=True,
                    history=history,
                )

            history.append("judge NO")

        raise HashlineEditExhaustedError(
            f"hashline_diff could not satisfy the requirement in {max_iter} iterations",
            iterations=llm_calls,
            last_source=current,
            last_error=last_error,
        )

    # ─── Internals ──────────────────────────────────────────────────────
    def _parse_hashline_diff_response(self, resp: str) -> list[HashlineOp] | None:
        """Parse an LLM response into a list of `HashlineOp`s in document order.

        Returns `None` on any parse/validation failure (caller re-prompts).
        """
        # Collect (left_delimiter_pos, kind, header, body) for every op of every
        # kind, then sort by position to preserve document order across kinds.
        # `cap2_all` returns (header, body) tuples per kind in document order;
        # we step the `find` cursor forward per block of the same kind to get
        # each block's actual position (not all 0).
        positioned: list[tuple[int, str, str, str]] = []
        for kind, capture, left in (
            ("set_line", HashlineSetCapture, HashlineDelimiters.SET_LEFT.value),
            ("replace_lines", HashlineRangeCapture, HashlineDelimiters.RANGE_LEFT.value),
            ("insert_after", HashlineInsertAfterCapture, HashlineDelimiters.INSERT_LEFT.value),
            ("replace", HashlineReplaceCapture, HashlineDelimiters.REPLACE_LEFT.value),
        ):
            cursor = 0
            for header, body in capture.cap2_all(resp):
                pos = resp.find(left, cursor)
                if pos == -1:
                    continue
                positioned.append((pos, kind, header, body))
                cursor = pos + len(left)

        positioned.sort(key=lambda x: x[0])

        edits: list[HashlineOp] = []
        for _, kind, header, body in positioned:
            edit = self._parse_block(kind, header, body)
            if edit is None:
                return None
            edits.append(edit)

        if not edits:
            return None
        return edits

    def _parse_block(self, kind: str, header: str, body: str) -> HashlineOp | None:
        r"""Parse one fenced block into a `HashlineOp`, or None on failure.

        `header` is the line between the opener and the first newline
        (e.g. `"2:b2"`, `"3:83 4:5f"`, or `""` for replace which has no header).
        `body` is everything between the first newline and the closer.

        Block shapes:
          - set_line:        header=`<anchor>`, body=`<new_text>`
          - replace_lines:   header=`<start_anchor> <end_anchor>`, body=`<new_text>`
          - insert_after:    header=`<anchor>`, body=`<text>`        (text must be non-empty)
          - replace:         header=`` (no inline header) or `"ALL"`, body=`<old_text>\n<new_text>`
        """
        if kind == "set_line":
            return self._parse_set_line(header, body)
        if kind == "replace_lines":
            return self._parse_replace_lines(header, body)
        if kind == "insert_after":
            return self._parse_insert_after(header, body)
        if kind == "replace":
            return self._parse_replace(header, body)
        return None

    @staticmethod
    def _valid_anchor(anchor: str) -> bool:
        """True if `anchor` parses as a valid `LINE:HASH` ref.

        `parse_hashline_anchor` raises `RuntimeError` on invalid format; we
        catch and return False so the parser can reject the whole response
        cleanly via `None` instead of leaking the exception.
        """
        try:
            return bool(parse_hashline_anchor(anchor))
        except RuntimeError:
            return False

    def _parse_set_line(self, header: str, payload: str) -> HashlineOp | None:
        anchor = header.strip()
        if not anchor or not self._valid_anchor(anchor):
            return None
        return HashlineOp(kind="set_line", anchor=anchor, new_text=payload)

    def _parse_replace_lines(self, header: str, payload: str) -> HashlineOp | None:
        parts = header.split(None, 1)
        if len(parts) != 2:
            return None
        start, end = parts[0].strip(), parts[1].strip()
        if not start or not end:
            return None
        if not self._valid_anchor(start) or not self._valid_anchor(end):
            return None
        return HashlineOp(
            kind="replace_lines",
            start_anchor=start,
            end_anchor=end,
            new_text=payload,
        )

    def _parse_insert_after(self, header: str, payload: str) -> HashlineOp | None:
        anchor = header.strip()
        if not anchor or not self._valid_anchor(anchor):
            return None
        if not payload:
            return None  # Catch the empty-text mistake here.
        return HashlineOp(kind="insert_after", anchor=anchor, text=payload)

    def _parse_replace(self, header: str, payload: str) -> HashlineOp | None:
        # REPLACE blocks have no inline anchor header. The format is:
        #   <<<<REPLACE\n<old_text>\n<new_text>\nREPLACE<<<<
        #   <<<<REPLACE ALL\n<old_text>\n<new_text>\nREPLACE<<<<
        # When `ALL` is the only thing on the header line, `payload` is
        # `<old_text>\n<new_text>`. Otherwise the LLM has put the header on
        # the opener line — we treat the rest of the line as `old_text`.
        if header.strip() == "ALL":
            old_nl = payload.find("\n")
            if old_nl == -1:
                return None
            return self._make_replace_op(old_text=payload[:old_nl], new_text=payload[old_nl + 1 :], all_flag=True)
        # `header` is whatever the LLM put on the opener line (usually empty).
        # The full old_text is the first line of (header + payload).
        combined = (header + ("\n" if header and payload else "") + payload).lstrip("\n")
        if not combined:
            return None
        nl = combined.find("\n")
        if nl == -1:
            # No newline → just old_text, new_text is empty
            return self._make_replace_op(old_text=combined, new_text="", all_flag=False)
        return self._make_replace_op(old_text=combined[:nl], new_text=combined[nl + 1 :], all_flag=False)

    def _make_replace_op(self, old_text: str, new_text: str, all_flag: bool) -> HashlineOp | None:
        if not old_text:
            return None
        return HashlineOp(kind="replace", old_text=old_text, new_text=new_text, all=all_flag)

    def _apply_edits(self, content: str, edits: list[HashlineOp]) -> str:
        """Apply a list of `HashlineOp`s sequentially, threading content through.

        Each op delegates to the corresponding Rust primitive.

        Raises:
            ValueError: On invalid op construction (shouldn't happen if parser
                succeeded).
            RuntimeError: On any `HashlineError` from the Rust side.
        """
        handlers = {
            "set_line": self._apply_set_line,
            "replace_lines": self._apply_replace_lines,
            "insert_after": self._apply_insert_after,
            "replace": self._apply_replace,
        }
        current = content
        for edit in edits:
            handler = handlers.get(edit.kind)
            if handler is None:
                raise ValueError(f"unknown edit kind: {edit.kind!r}")
            current = handler(current, edit)
        return current

    def _apply_set_line(self, content: str, edit: HashlineOp) -> str:
        if edit.anchor is None or edit.new_text is None:
            raise ValueError("set_line requires anchor and new_text")
        return apply_set_line(content, edit.anchor, edit.new_text)

    def _apply_replace_lines(self, content: str, edit: HashlineOp) -> str:
        if edit.start_anchor is None or edit.end_anchor is None or edit.new_text is None:
            raise ValueError("replace_lines requires start_anchor, end_anchor, new_text")
        return apply_replace_lines(content, edit.start_anchor, edit.end_anchor, edit.new_text)

    def _apply_insert_after(self, content: str, edit: HashlineOp) -> str:
        if edit.anchor is None or edit.text is None:
            raise ValueError("insert_after requires anchor and text")
        if not edit.text:
            raise ValueError("insert_after requires non-empty text")
        return apply_insert_after(content, edit.anchor, edit.text)

    def _apply_replace(self, content: str, edit: HashlineOp) -> str:
        if edit.old_text is None or edit.new_text is None:
            raise ValueError("replace requires old_text and new_text")
        return apply_replace(content, edit.old_text, edit.new_text, edit.all)


__all__ = [
    "HashlineDiffResult",
    "HashlineEdit",
    "HashlineEditExhaustedError",
    "HashlineOp",
]
