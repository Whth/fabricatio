"""Content probes: the term lists a corpus wants the benchmark to use.

A probe belongs to a corpus, not to this package — whether a prop is unplanned,
a register is drifting, or two names denote one object depends on the novel, its
language and its genre — so the lists are supplied per corpus instead of being
baked in. Measured hits are only ever reported against the run's own plan tree:
the outline, the metadata and the bible license the vocabulary a novel may use.

Without a probe file the benchmark still measures everything corpus-independent
(export integrity, script fidelity, repetition, sentence rhythm, vocabulary
repeats and length against target); the probe rows then read as not configured.

A probe file is JSON with three optional sections::

    {
      "gated":    ["spyglass", "brass compass"],
      "watch":    ["sapphire"],
      "aliases":  [["lamp", "lantern"]]
    }

``gated`` terms fail the run when they appear in the prose. ``watch`` terms are
counted and reported per 1000 characters, twice: raw, and unlicensed — a term the
outline or the bible uses itself is licensed vocabulary, not drift. Each
``aliases`` group lists names for one object; a run that mixes two names of a
group inside one novel gets a warning.

Load a file with ``TermProbes.load`` and pass it to ``score_run(run_dir, probes=…)``,
or hand the path to ``fanvl bench --probes`` / the ``benchmark_probes``
configuration key, which the post-run report reads.
"""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field


class TermProbes(BaseModel):
    """Term lists the benchmark scores a run with."""

    model_config = ConfigDict(frozen=True)

    gated: frozenset[str] = Field(default_factory=frozenset)
    """Terms that fail the run when they appear in the prose."""

    watch: frozenset[str] = Field(default_factory=frozenset)
    """Terms counted per 1000 characters; reported, never gated."""

    aliases: tuple[tuple[str, ...], ...] = ()
    """Groups of interchangeable names; mixing two names of one group is a warning."""

    @classmethod
    def load(cls, path: Path) -> Self:
        """Read a probe file, raising ``OSError`` when it is unreadable and ``ValueError`` when it does not fit."""
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
