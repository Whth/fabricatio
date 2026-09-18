"""Content probes: the term lists a corpus wants the benchmark to use.

A probe belongs to a corpus, not to this package — whether a prop is unplanned,
a register is drifting, or two names denote one object depends on the novel, its
language and its genre — so the lists are supplied per corpus instead of being
baked in. Measured hits are only ever reported against the run's own plan tree:
a watch term the outline or the bible uses itself is licensed vocabulary, not
drift.

Without a probe table the benchmark still measures everything
corpus-independent (export integrity, script fidelity, repetition, sentence
rhythm, vocabulary repeats and length against target); the probe rows then read
as not configured.

The table is one file — TOML by preference, JSON accepted — with three optional
sections::

    gated   = ["spyglass", "brass compass"]      # every occurrence fails the run
    watch   = ["hologram", "sapphire"]           # counted per 1000 characters
    aliases = [["lamp", "lantern"]]              # mixed names for one object

``fanvl bench score|compare|board|scan`` read one table: the ``--probes`` path,
which defaults to :attr:`TermProbes.FILENAME` in the working directory — so a
corpus that keeps its table beside its novels never repeats a path. A path that
does not exist skips the probe rows instead of failing a command. ``fanvl bench
scan`` runs the same table over prose that carries no run directory: manuscripts,
chapter files, drafts.
"""

import tomllib
from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field


class TermProbes(BaseModel):
    """Term lists the benchmark scores a run with."""

    model_config = ConfigDict(frozen=True)

    FILENAME: ClassVar[str] = "probes.toml"
    """The table a project keeps in its working directory; the default when nothing else names one."""

    gated: frozenset[str] = Field(default_factory=frozenset)
    """Terms that fail the run when they appear in the prose."""

    watch: frozenset[str] = Field(default_factory=frozenset)
    """Terms counted per 1000 characters; reported, never gated."""

    aliases: tuple[tuple[str, ...], ...] = ()
    """Groups of interchangeable names; mixing two names of one group is a warning."""

    @classmethod
    def load(cls, path: Path) -> Self:
        """Read a probe table, raising ``OSError`` when it is unreadable and ``ValueError`` when it does not fit.

        A ``.toml`` file is parsed as TOML, every other suffix as JSON.
        """
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".toml":
            return cls.model_validate(tomllib.loads(text))
        return cls.model_validate_json(text)

    @classmethod
    def resolve(cls, path: Path | None = None) -> Self | None:
        """The table at ``path``, defaulting to :attr:`FILENAME` in the working directory.

        Returns ``None`` when that path does not exist, so a project without a
        table simply measures the corpus-independent metrics. Raises ``OSError``
        when the file exists but is unreadable and ``ValueError`` when it does not
        fit the schema.
        """
        table = Path(cls.FILENAME) if path is None else path
        return cls.load(table) if table.is_file() else None
