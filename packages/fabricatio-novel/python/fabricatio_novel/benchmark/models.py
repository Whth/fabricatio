"""Scorecard models: one run's measured quality, and the delta against a baseline.

Every number is derived from artifacts the pipeline already persisted, so a
scorecard can be recomputed at any time and two scorecards are comparable when
their ``plan_fingerprint`` matches — that means the plan tree was byte-identical
and only the writing side changed, which makes the per-scene pairs a controlled
comparison instead of two independent samples.

Each model owns how it is read and measured, as classmethod factories: reading a
run's files (``StageArtifact.collect``, ``StageArtifact.load``,
``SceneRef.collect``) and measuring what the run wrote (``SceneScore.of``,
``RepetitionScore.of``, ``ProbeScore.of``, ...). A scorecard is the composition
of those factories, so no measurement is derived twice and nothing that belongs
to a model is left floating beside it.

Each model also carries the printed form of the numbers a report shows as
``*_display`` computed fields: the handlebars registry has no arithmetic
helpers, so rounding, percentages and unit conversion happen here, next to the
measurement they belong to, and the report templates read the dump as-is.

A report table is measured and rendered here too (``Table``): handlebars can
neither measure a column nor pad a cell, so the models hand the templates a
finished table.
"""

import hashlib
import json
import statistics
from collections import Counter
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Self

from fabricatio_core.rust import word_count
from pydantic import BaseModel, ConfigDict, Field, ValidationError, computed_field

from fabricatio_novel.benchmark.enums import Gate, Metric, Verdict
from fabricatio_novel.benchmark.probes import TermProbes
from fabricatio_novel.benchmark.text import char_gram_stream, cjk_ratio, ngram_overlap, sentences, significant_terms
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext
from fabricatio_novel.models.context.rag import RagStoryContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext


@dataclass(frozen=True, slots=True)
class SceneRef:
    """One scene's position in the manuscript and the three context levels it hangs from."""

    index: int
    chapter: ChapterContext
    story: StoryContext
    scene: SceneContext

    @classmethod
    def collect(cls, novel: NovelContext) -> list[Self]:
        """Flatten the context tree into manuscript order."""
        refs: list[Self] = []
        for chapter in novel.child_contexts:
            for story in chapter.child_contexts:
                for scene in story.child_contexts:
                    refs.append(cls(index=len(refs) + 1, chapter=chapter, story=story, scene=scene))
        return refs


class StageArtifact(BaseModel):
    """One persisted stage snapshot of a run."""

    model_config = ConfigDict(frozen=True)

    name: str
    path: str
    digest: str
    chars: int
    modified: datetime

    @classmethod
    def collect(cls, run_dir: Path) -> list[Self]:
        """Read the persisted stage snapshots of a run, in name order."""
        stages: list[Self] = []
        for stage_dir in sorted(path for path in run_dir.iterdir() if path.is_dir() and path.name.startswith("stage_")):
            snapshot = next(stage_dir.glob("*.json"), None)
            if snapshot is None:
                continue
            body = snapshot.read_bytes()
            stages.append(
                cls(
                    name=stage_dir.name,
                    path=str(snapshot),
                    digest=hashlib.md5(body, usedforsecurity=False).hexdigest()[:12],
                    chars=len(body),
                    modified=datetime.fromtimestamp(snapshot.stat().st_mtime, tz=UTC).astimezone(),
                )
            )
        return stages

    def load(self) -> NovelContext:
        """Read this snapshot back into the pipeline's own context model.

        A snapshot whose stories carry their ``rag`` settings restores as
        :class:`RagNovelContext`, which brings the sealed stories' retrieval
        state back through the chapter's type-constrained children; plain
        snapshots fail that stricter validation and load as :class:`NovelContext`.
        The dispatch is decided by the data's shape, never by per-item repair.
        """
        data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        try:
            return RagNovelContext.model_validate(data)
        except ValidationError:
            return NovelContext.model_validate(data)

    def load_optional(self) -> NovelContext | None:
        """Read this snapshot, returning ``None`` for a stage that does not validate as the pipeline's own tree."""
        try:
            return self.load()
        except ValueError:
            return None

    @classmethod
    def newest_with_prose(cls, stages: Sequence[Self]) -> Self:
        """Return the newest stage carrying composed prose, i.e. the finished manuscript.

        Raises ``ValueError`` when no snapshot carries composed prose: a run that
        never reached the writing stage cannot be scored.
        """
        for stage in reversed(stages):
            novel = stage.load_optional()
            if novel is not None and any(ref.scene.content for ref in SceneRef.collect(novel)):
                return stage
        raise ValueError("no stage snapshot carries composed prose")


class SceneScore(BaseModel):
    """One scene: its budget and its actual size, both in the pipeline's own words."""

    model_config = ConfigDict(frozen=True)

    index: int
    story: str
    title: str
    words: int
    target: int
    ratio: float

    @classmethod
    def of(cls, ref: SceneRef) -> Self:
        """Measure one scene's size against its planned word count, in the pipeline's own words."""
        words = word_count(ref.scene.content)
        target = ref.scene.expected_word_count
        return cls(
            index=ref.index,
            story=ref.story.title,
            title=ref.scene.title,
            words=words,
            target=target,
            ratio=words / target if target > 0 else 0.0,
        )


class StoryScore(BaseModel):
    """One story's share of the run, in the pipeline's own words."""

    model_config = ConfigDict(frozen=True)

    title: str
    scenes: int
    words: int
    target: int
    ratio: float

    @classmethod
    def from_scene_scores(cls, scores: Sequence[SceneScore]) -> list[Self]:
        """Aggregate the measured scenes into their stories, in manuscript order."""
        totals: dict[str, tuple[int, int, int]] = {}
        for score in scores:
            scenes, words, target = totals.get(score.story, (0, 0, 0))
            totals[score.story] = (scenes + 1, words + score.words, target + score.target)
        return [
            cls(title=title, scenes=scenes, words=words, target=target, ratio=words / target if target > 0 else 0.0)
            for title, (scenes, words, target) in totals.items()
        ]


class BoundaryEcho(BaseModel):
    """A scene seam where the next scene's opening repeats this scene's closing stretch.

    The pipeline strips a *verbatim* prefix a scene re-emits, so what survives here is
    the boundary written twice in slightly different words — the same moment staged at
    the end of one scene and again at the top of the next.
    """

    model_config = ConfigDict(frozen=True)

    scene: int
    next_scene: int
    title: str
    next_title: str
    overlap: float

    @computed_field
    @property
    def overlap_display(self) -> str:
        """The overlap as a report prints it."""
        return f"{self.overlap:.0%}"


class DuplicateSentence(BaseModel):
    """A sentence emitted verbatim in more than one scene."""

    model_config = ConfigDict(frozen=True)

    scenes: list[int]
    text: str


SHINGLE_SIZE = 12
"""Character n-gram length for cross-scene repetition; long enough that sharing one means more than shared vocabulary."""

ECHO_SIZE = 8
"""Character n-gram length for seam echoes; short enough to survive a paraphrase at the seam."""

ECHO_WINDOW = 300
"""Characters taken from each side of a seam when measuring an echo."""

ECHO_WARN = 0.05
"""Echo overlap above which the seam is worth a look; clean runs measured under 0.03, seams that restaged the previous scene 0.10-0.14."""

DUPLICATE_MIN_CHARS = 10
"""Shortest whitespace-normalized sentence counted as a verbatim duplicate; shorter fragments match across ordinary narration."""


class RepetitionScore(BaseModel):
    """How much the prose repeats itself."""

    model_config = ConfigDict(frozen=True)

    shingle_size: int
    max_pair_overlap: float
    mean_pair_overlap: float
    boundary_echoes: list[BoundaryEcho] = Field(default_factory=list)
    loud_echoes: list[BoundaryEcho] = Field(default_factory=list)
    """The seams whose echo exceeds the warning threshold; filled when scoring, so no report re-filters them."""
    max_boundary_echo: float = 0.0
    duplicate_sentences: list[DuplicateSentence] = Field(default_factory=list)

    @computed_field
    @property
    def max_echo_display(self) -> str:
        """The worst seam echo as a report prints it."""
        return f"{self.max_boundary_echo:.0%}"

    @computed_field
    @property
    def max_pair_display(self) -> str:
        """The worst cross-scene overlap as a report prints it."""
        return f"{self.max_pair_overlap:.2%}"

    @classmethod
    def of(cls, refs: Sequence[SceneRef]) -> Self:
        """Measure how much the prose repeats itself: scene pairs, seams and verbatim sentences."""
        proses = [ref.scene.content for ref in refs]
        overlaps = [
            ngram_overlap(left, right, SHINGLE_SIZE)
            for index, left in enumerate(proses)
            for right in proses[index + 1 :]
        ]
        echoes = [
            BoundaryEcho(
                scene=refs[index].index,
                next_scene=refs[index + 1].index,
                title=refs[index].scene.title,
                next_title=refs[index + 1].scene.title,
                overlap=ngram_overlap(
                    refs[index].scene.content[-ECHO_WINDOW:], refs[index + 1].scene.content[:ECHO_WINDOW], ECHO_SIZE
                ),
            )
            for index in range(len(refs) - 1)
        ]
        seen: dict[str, list[int]] = {}
        for index, prose in enumerate(proses, start=1):
            for sentence in set(sentences(prose)):
                if len(sentence) >= DUPLICATE_MIN_CHARS:
                    seen.setdefault(sentence, []).append(index)
        duplicates = [DuplicateSentence(scenes=scenes, text=text) for text, scenes in seen.items() if len(scenes) > 1]
        return cls(
            shingle_size=SHINGLE_SIZE,
            max_pair_overlap=max(overlaps, default=0.0),
            mean_pair_overlap=sum(overlaps) / len(overlaps) if overlaps else 0.0,
            boundary_echoes=echoes,
            loud_echoes=[echo for echo in echoes if echo.overlap > ECHO_WARN],
            max_boundary_echo=max((echo.overlap for echo in echoes), default=0.0),
            duplicate_sentences=duplicates,
        )


class Tally(BaseModel):
    """One repeated token and how often it occurs."""

    model_config = ConfigDict(frozen=True)

    text: str
    count: int


LONG_SENTENCE_CHARS = 80
"""A sentence from here on counts as long: about fifteen English words, a run-on in Chinese."""


class SentenceScore(BaseModel):
    """How long a run's sentences are and how much their lengths vary."""

    model_config = ConfigDict(frozen=True)

    count: int = 0
    mean_chars: float = 0.0
    median_chars: float = 0.0
    max_chars: int = 0
    variation: float = 0.0
    """The coefficient of variation (stdev / mean): how much long and short sentences mix."""
    long_ratio: float = 0.0
    """The share of sentences at or above the long-sentence threshold."""

    @classmethod
    def of(cls, text: str) -> Self:
        """Measure the sentence lengths of the composed prose.

        A sentence's length is its character count, the ender that closes it
        included; the splitter already collapsed every whitespace run to a single
        space, so an English word gap counts once and Chinese and English runs are
        counted by the same rule.
        """
        lengths = [len(sentence) for sentence in sentences(text)]
        mean = statistics.fmean(lengths) if lengths else 0.0
        return cls(
            count=len(lengths),
            mean_chars=mean,
            median_chars=statistics.median(lengths) if lengths else 0.0,
            max_chars=max(lengths, default=0),
            variation=statistics.pstdev(lengths) / mean if mean else 0.0,
            long_ratio=(
                sum(1 for length in lengths if length >= LONG_SENTENCE_CHARS) / len(lengths) if lengths else 0.0
            ),
        )

    @computed_field
    @property
    def mean_display(self) -> str:
        """The mean sentence length as a report prints it."""
        return f"{self.mean_chars:.1f}"

    @computed_field
    @property
    def median_display(self) -> str:
        """The median sentence length as a report prints it."""
        return f"{self.median_chars:.1f}"

    @computed_field
    @property
    def variation_display(self) -> str:
        """The length variation as a report prints it."""
        return f"{self.variation:.2f}"

    @computed_field
    @property
    def long_display(self) -> str:
        """The long-sentence share as a report prints it."""
        return f"{self.long_ratio:.0%}"


VOCAB_GRAM_SIZE = 3
"""Characters per vocabulary n-gram.

Characters, not words: the same stream measures every script, so no metric has
to know which language the run is in. Three characters are a word in Chinese
and a word fragment in English, which is why the numbers compare runs of one
corpus rather than prose in the abstract.
"""

VOCAB_WINDOW_GRAMS = 1000
"""n-grams per vocabulary window.

A run is measured window by window and the windows are averaged, so the number
does not follow the run's length: without this, a long run would always look
more repetitive than a short one, because it gave its n-grams more chances to
meet again.
"""

VOCAB_TOPS = 8
"""How many repeated n-grams a scorecard names."""


class VocabularyScore(BaseModel):
    """How much short vocabulary the run recycles.

    Measured in character n-grams: unlike a word count this needs no word
    boundaries and no stopword list, so Chinese and English runs go through the
    same rule and the number stays a relative signal between runs of one corpus.
    Calibration against audited runs is why the compared number counts repeats
    *inside* a window rather than over the whole manuscript: over the whole
    manuscript the value mostly tracks the run's length, inside a window it moves
    with the prose (measured 82..106 per 1000 across one corpus).
    """

    model_config = ConfigDict(frozen=True)

    gram_size: int = 0
    """How many characters one n-gram spans."""

    grams: int = 0
    """How many n-grams the composed prose holds."""

    window_grams: int = 0
    """How many n-grams one measurement window holds."""

    recycled_per_1k: float = 0.0
    """The mean number of n-grams per 1000 that repeat inside their own window."""

    top: list[Tally] = Field(default_factory=list)
    """The most repeated n-grams of the whole run; for reading, not for comparing."""

    @classmethod
    def of(cls, text: str) -> Self:
        """Measure the n-gram vocabulary of the composed prose, one window at a time."""
        grams = char_gram_stream(text, VOCAB_GRAM_SIZE)
        windows = [
            grams[start : start + VOCAB_WINDOW_GRAMS]
            for start in range(0, len(grams) - VOCAB_WINDOW_GRAMS + 1, VOCAB_WINDOW_GRAMS)
        ]
        if not windows and grams:
            # Prose shorter than one window is measured as the single window it fits in.
            windows = [grams]
        recycled = [
            sum(count for count in Counter(window).values() if count > 1) / len(window) * 1000 for window in windows
        ]
        return cls(
            gram_size=VOCAB_GRAM_SIZE,
            grams=len(grams),
            window_grams=VOCAB_WINDOW_GRAMS,
            recycled_per_1k=statistics.fmean(recycled) if recycled else 0.0,
            top=[Tally(text=gram, count=count) for gram, count in Counter(grams).most_common(VOCAB_TOPS)],
        )

    @computed_field
    @property
    def recycled_display(self) -> str:
        """The recycled n-gram rate as a report prints it."""
        return f"{self.recycled_per_1k:.1f}"


class ProseScore(BaseModel):
    """How the prose is written: sentence rhythm and vocabulary repeats.

    Both measures stay language-neutral: sentences are split at the enders both
    scripts share and counted in characters, and the vocabulary is character
    n-grams, so nothing here needs to know which language the run is in.
    """

    model_config = ConfigDict(frozen=True)

    sentences: SentenceScore = Field(default_factory=SentenceScore)
    vocabulary: VocabularyScore = Field(default_factory=VocabularyScore)

    @classmethod
    def of(cls, text: str) -> Self:
        """Measure the composed prose of a run."""
        return cls(sentences=SentenceScore.of(text), vocabulary=VocabularyScore.of(text))


class ChannelScore(BaseModel):
    """The RAG reference channel of the run: the documents each story retrieved, read from the stories' retrieved styles."""

    model_config = ConfigDict(frozen=True)

    docs_per_story: list[int] = Field(default_factory=list)
    doc_chars: int = 0

    @classmethod
    def of(cls, novel: NovelContext) -> Self:
        """Measure the reference channel: how many documents each story got, and their total size."""
        stories = [story for chapter in novel.child_contexts for story in chapter.child_contexts]
        documents = [list(story.retrieved_styles) if isinstance(story, RagStoryContext) else [] for story in stories]
        return cls(
            docs_per_story=[len(docs) for docs in documents],
            doc_chars=sum(len(doc) for docs in documents for doc in docs),
        )


class LanguageScore(BaseModel):
    """Script fidelity of the prose against the script of the outline."""

    model_config = ConfigDict(frozen=True)

    declared: str
    outline_cjk_ratio: float
    prose_cjk_ratio: float
    expected_cjk: bool

    @classmethod
    def of(cls, novel: NovelContext, prose: str) -> Self:
        """Compare the script of the composed prose with the script of the outline it was written from."""
        outline_ratio = cjk_ratio(novel.outline)
        return cls(
            declared=novel.language,
            outline_cjk_ratio=outline_ratio,
            prose_cjk_ratio=cjk_ratio(prose),
            expected_cjk=outline_ratio >= 0.5,
        )

    @computed_field
    @property
    def prose_cjk_display(self) -> str:
        """The prose's CJK share as a report prints it."""
        return f"{self.prose_cjk_ratio:.0%}"

    @computed_field
    @property
    def outline_cjk_display(self) -> str:
        """The outline's CJK share as a report prints it."""
        return f"{self.outline_cjk_ratio:.0%}"


class IntegrityScore(BaseModel):
    """The export's structural integrity."""

    model_config = ConfigDict(frozen=True)

    chapter_files: int
    concat_mismatches: list[str] = Field(default_factory=list)
    epub_bytes: int | None = None
    empty_scenes: list[int] = Field(default_factory=list)

    @classmethod
    def of(cls, run_dir: Path, refs: Sequence[SceneRef]) -> Self:
        """Check that the exported chapter text matches the scenes, and report export size and empty scenes."""
        chapters: dict[str, list[str]] = {}
        for ref in refs:
            chapters.setdefault(ref.chapter.title, []).append(ref.scene.content)
        chapter_dir = run_dir / "chapters"
        chapter_files = sorted(chapter_dir.glob("*.txt")) if chapter_dir.is_dir() else []
        mismatches = [
            f"{path.name}: exported {len(path.read_text(encoding='utf-8').strip())} chars "
            f"vs {len(prose.strip())} chars from the scenes"
            for index, prose in enumerate(("\n\n".join(scenes) for scenes in chapters.values()), start=1)
            if (path := next((path for path in chapter_files if path.stem == f"{index:02d}"), None)) is not None
            and path.read_text(encoding="utf-8").strip() != prose.strip()
        ]
        epub = next(run_dir.glob("*.epub"), None)
        return cls(
            chapter_files=len(chapter_files),
            concat_mismatches=mismatches,
            epub_bytes=epub.stat().st_size if epub is not None else None,
            empty_scenes=[ref.index for ref in refs if not ref.scene.content.strip()],
        )

    @computed_field
    @property
    def epub_mb_display(self) -> str | None:
        """The export's size in megabytes as a report prints it; ``None`` when the run has no EPUB."""
        return None if self.epub_bytes is None else f"{self.epub_bytes / 1e6:.1f}"


class ProbeScore(BaseModel):
    """What the term probes measured; every field stays at its default without a probe file."""

    model_config = ConfigDict(frozen=True)

    configured: bool = False
    """Whether the run was scored against a probe file."""

    gated: dict[str, int] = Field(default_factory=dict)
    """Counts of the gated terms present in the prose; any hit fails the run."""

    watch: dict[str, int] = Field(default_factory=dict)
    """Counts of the watch terms present in the prose."""

    watch_per_1k: float = 0.0
    """Watch-term occurrences per 1000 prose characters."""

    watch_unlicensed: dict[str, int] = Field(default_factory=dict)
    """Watch terms the outline, the metadata and the bible never use themselves."""

    aliases: dict[str, dict[str, int]] = Field(default_factory=dict)
    """Per alias group, keyed by its joined names: the variants the prose mixes and their counts."""

    @classmethod
    def of(cls, novel: NovelContext, prose: str, probes: TermProbes | None) -> Self:
        """Measure the supplied term probes; without a probe table every field stays at its default."""
        if probes is None:
            return cls()
        return cls.measured(prose, probes, licensed=cls._root_terms(novel))

    @classmethod
    def of_text(cls, prose: str, probes: TermProbes) -> Self:
        """Measure prose that carries no plan tree, so every watch hit counts as unlicensed vocabulary."""
        return cls.measured(prose, probes, licensed=frozenset())

    @classmethod
    def measured(cls, prose: str, probes: TermProbes, licensed: AbstractSet[str]) -> Self:
        """Count every probe term in the prose; ``licensed`` names the watch hits a plan tree uses itself."""
        watch = {term: prose.count(term) for term in probes.watch if term in prose}
        return cls(
            configured=True,
            gated={term: prose.count(term) for term in probes.gated if term in prose},
            watch=watch,
            watch_per_1k=sum(watch.values()) / len(prose) * 1000 if prose else 0.0,
            watch_unlicensed={term: count for term, count in watch.items() if term not in licensed},
            aliases={
                "|".join(group): counts
                for group in probes.aliases
                if len(counts := {term: prose.count(term) for term in group if term in prose}) >= 2
            },
        )

    @staticmethod
    def _root_terms(novel: NovelContext) -> set[str]:
        """Return the vocabulary the outline, the metadata and the bible use."""
        bible = novel.series_bible.as_prompt() if novel.series_bible is not None else ""
        return significant_terms(
            "\n".join(part for part in (novel.outline, novel.title, novel.description, bible) if part)
        )

    @computed_field
    @property
    def gated_total(self) -> int:
        """The gated terms' total occurrences."""
        return sum(self.gated.values())

    @computed_field
    @property
    def unlicensed_total(self) -> int:
        """The total occurrences of watch terms no outline, metadata or bible text uses."""
        return sum(self.watch_unlicensed.values())

    @computed_field
    @property
    def watch_display(self) -> str:
        """The watch-term rate as a report prints it."""
        return f"{self.watch_per_1k:.2f}"

    @computed_field
    @property
    def aliases_display(self) -> str:
        """The mixed alias groups as JSON, because a template prints a dict as ``[object]``."""
        return json.dumps(self.aliases, ensure_ascii=False)


class GateFailure(BaseModel):
    """A hard invariant the run violated."""

    model_config = ConfigDict(frozen=True)

    gate: Gate
    detail: str

    @classmethod
    def collect(cls, language: LanguageScore, integrity: IntegrityScore, probes: ProbeScore) -> list[Self]:
        """Collect the hard invariants a run must satisfy."""
        failures: list[Self] = []
        if language.expected_cjk != (language.prose_cjk_ratio >= 0.5):
            failures.append(
                cls(
                    gate=Gate.LANGUAGE,
                    detail=f"outline is {language.outline_cjk_ratio:.0%} CJK but the prose is {language.prose_cjk_ratio:.0%}",
                )
            )
        if integrity.concat_mismatches:
            failures.append(cls(gate=Gate.EXPORT_TEXT, detail="; ".join(integrity.concat_mismatches)))
        if integrity.empty_scenes:
            failures.append(cls(gate=Gate.EMPTY_SCENE, detail=f"scene(s) {integrity.empty_scenes} carry no prose"))
        if probes.gated:
            failures.append(
                cls(
                    gate=Gate.GATED_TERMS,
                    detail="probe terms that must not appear do: "
                    + ", ".join(f"{term}x{count}" for term, count in sorted(probes.gated.items())),
                )
            )
        return failures


LOW_SCENE_RATIO = 0.5
"""A scene below this fraction of its planned words is reported as possibly truncated."""

DUPLICATE_WARN = 1
"""Duplicates from here on are flagged; refrains and catchphrases legitimately repeat, so they never fail a run."""

WATCH_WARN_PER_1K = 2.0
"""Watch-term rate above which the run gets a warning; set the watch list so clean runs stay under it."""


class RunScorecard(BaseModel):
    """Everything the benchmark measured about one run."""

    model_config = ConfigDict(frozen=True)

    run: str
    run_dir: str
    scored_at: datetime
    started_at: datetime
    duration_s: float
    plan_fingerprint: str
    prose_fingerprint: str
    stages: dict[str, StageArtifact]

    chapters: int
    stories: list[StoryScore]
    scenes: list[SceneScore]
    scene_count: int
    target_words: int
    prose_words: int
    ratio: float
    scene_ratio_median: float
    scene_ratio_max: float

    repetition: RepetitionScore
    prose: ProseScore
    channel: ChannelScore
    language: LanguageScore
    integrity: IntegrityScore
    probes: ProbeScore

    gates_failed: list[GateFailure]
    warnings: list[str]

    @computed_field
    @property
    def minutes_display(self) -> str:
        """The wall time in minutes as a report prints it."""
        return f"{self.duration_s / 60:.1f}"

    @computed_field
    @property
    def ratio_display(self) -> str:
        """The prose-to-target ratio as a report prints it."""
        return f"{self.ratio:.2f}"

    @computed_field
    @property
    def scene_median_display(self) -> str:
        """The median scene ratio as a report prints it."""
        return f"{self.scene_ratio_median:.2f}"

    @computed_field
    @property
    def scene_max_display(self) -> str:
        """The largest scene ratio as a report prints it."""
        return f"{self.scene_ratio_max:.2f}"

    @property
    def passed(self) -> bool:
        """Whether every hard gate held."""
        return not self.gates_failed

    @property
    def board_row(self) -> tuple[str, ...]:
        """This run's cells on the board table, in column order."""
        return (
            self.run,
            self.minutes_display,
            str(self.scene_count),
            f"{self.ratio_display}x",
            self.repetition.max_echo_display,
            str(len(self.repetition.duplicate_sentences)),
            self.prose.sentences.mean_display,
            self.prose.vocabulary.recycled_display,
            str(self.probes.gated_total),
            self.probes.watch_display,
            "PASS" if self.passed else "FAIL",
        )

    @classmethod
    def warnings_of(cls, scenes: Sequence[SceneScore], repetition: RepetitionScore, probes: ProbeScore) -> list[str]:
        """Collect the soft signals that deserve a look but do not fail a run."""
        notes: list[str] = []
        short = [score for score in scenes if 0 < score.ratio < LOW_SCENE_RATIO]
        if short:
            notes.append(
                "scenes below half their target: " + ", ".join(f"{score.index} ({score.ratio:.2f}x)" for score in short)
            )
        if repetition.loud_echoes:
            notes.append(
                "seam echo: "
                + ", ".join(
                    f"scene {echo.scene}->{echo.next_scene} repeats {echo.overlap:.0%} of its closing stretch"
                    for echo in repetition.loud_echoes
                )
            )
        if len(repetition.duplicate_sentences) >= DUPLICATE_WARN:
            example = repetition.duplicate_sentences[0]
            notes.append(
                f"{len(repetition.duplicate_sentences)} sentence(s) repeated verbatim across scenes, e.g. scene(s) "
                f"{example.scenes}: {example.text[:60]}"
            )
        if repetition.max_pair_overlap > ECHO_WARN:
            notes.append(f"cross-scene {repetition.shingle_size}-gram overlap {repetition.max_pair_overlap:.2%}")
        if probes.watch_per_1k > WATCH_WARN_PER_1K:
            notes.append(f"probe watch rate {probes.watch_per_1k:.2f}/1k chars")
        return notes


class MetricDelta(BaseModel):
    """One continuous metric's change between two scorecards."""

    model_config = ConfigDict(frozen=True)

    metric: Metric
    baseline: float
    candidate: float
    relative_change: float | None
    """Change as a fraction of the baseline (0.2 means +20%); ``None`` when the baseline is zero."""
    verdict: Verdict
    """``Verdict.IMPROVED``, ``Verdict.REGRESSED``, ``Verdict.DRIFTED`` for a directionless metric that moved off its baseline, or ``Verdict.NOISE`` while the change stays inside the band."""

    @computed_field
    @property
    def baseline_display(self) -> str:
        """The baseline value as the comparison table prints it."""
        return f"{self.baseline:.3f}"

    @computed_field
    @property
    def candidate_display(self) -> str:
        """The candidate value as the comparison table prints it."""
        return f"{self.candidate:.3f}"

    @computed_field
    @property
    def change_display(self) -> str:
        """The relative change as the comparison table prints it; ``n/a`` when the baseline is zero."""
        return "n/a" if self.relative_change is None else f"{self.relative_change:+.1%}"

    @property
    def cells(self) -> tuple[str, ...]:
        """This delta's cells on the metric table, in column order."""
        return (
            self.metric.value,
            self.baseline_display,
            self.candidate_display,
            self.change_display,
            self.verdict.value,
        )


class TableColumn(BaseModel):
    """One column of a report table: the heading above it, its width and the side its cells sit on."""

    model_config = ConfigDict(frozen=True)

    label: str
    """The heading printed above the column."""

    width: int
    """Character width the heading and every cell of the column are padded to."""

    right_aligned: bool = False
    """Whether the cells sit against the right edge, as numbers do, instead of the left, as text does."""

    @classmethod
    def measured(cls, label: str, cells: Sequence[str], *, right_aligned: bool = False) -> Self:
        """Measure a column whose heading and cells are padded to their widest entry."""
        return cls(
            label=label,
            width=max(len(label), max((len(cell) for cell in cells), default=0)),
            right_aligned=right_aligned,
        )

    def padded(self, cell: str) -> str:
        """The cell padded to this column's width."""
        return cell.rjust(self.width) if self.right_aligned else cell.ljust(self.width)


class Table(BaseModel):
    """A pipe table as a report prints it: its measured columns and the cells of every row."""

    model_config = ConfigDict(frozen=True)

    columns: list[TableColumn]
    """The columns in print order; every row carries one cell per column, in the same order."""

    rows: list[list[str]]
    """The body cells, one list per row."""

    @classmethod
    def measured(cls, columns: Sequence[tuple[str, bool]], rows: Sequence[tuple[str, ...]]) -> Self:
        """Measure a table from its headings in print order and the cells of every row.

        Each entry of ``columns`` is a heading and whether its cells sit against
        the right edge; a column is as wide as its heading and its widest cell.
        """
        return cls(
            columns=[
                TableColumn.measured(label, [row[index] for row in rows], right_aligned=right_aligned)
                for index, (label, right_aligned) in enumerate(columns)
            ],
            rows=[list(row) for row in rows],
        )

    @computed_field
    @property
    def display(self) -> str:
        """The table as a report prints it: heading, rule row and every cell padded to its column."""
        rule = "|" + "|".join("-" * (column.width + 2) for column in self.columns) + "|"

        def line(cells: Sequence[str]) -> str:
            padded = [column.padded(cell) for column, cell in zip(self.columns, cells, strict=True)]
            return "| " + " | ".join(padded) + " |"

        return "\n".join([line([column.label for column in self.columns]), rule, *(line(row) for row in self.rows)])


class Board(Table):
    """The newest runs side by side, measured into the table they print."""

    COLUMNS: ClassVar[tuple[tuple[str, bool], ...]] = (
        ("run", False),
        ("min", True),
        ("scenes", True),
        ("ratio", True),
        ("echo", True),
        ("dup", True),
        ("sent", True),
        ("vocab", True),
        ("gated", True),
        ("watch/1k", True),
        ("gates", False),
    )
    """The board's headings in print order, each with whether its cells sit against the right edge."""

    @classmethod
    def of(cls, cards: Sequence[RunScorecard]) -> Self:
        """Measure the board's table over the given runs, in the order they are given in."""
        return cls.measured(cls.COLUMNS, [card.board_row for card in cards])


class ProseScan(BaseModel):
    """One text file measured against the probe table, without a run directory behind it."""

    model_config = ConfigDict(frozen=True)

    path: str
    """The file, as the command that measured it named it."""

    chars: int
    """How many characters of text were measured."""

    probes: ProbeScore

    @classmethod
    def of(cls, path: Path, probes: TermProbes) -> Self:
        """Read one text file and measure it against the table.

        Raises ``OSError`` when the file is unreadable and ``UnicodeDecodeError``
        when it is not UTF-8.
        """
        prose = path.read_text(encoding="utf-8")
        return cls(path=str(path), chars=len(prose), probes=ProbeScore.of_text(prose, probes))

    @property
    def passed(self) -> bool:
        """Whether no gated term was found; mixed alias groups are reported, never fatal."""
        return not self.probes.gated

    @property
    def cells(self) -> tuple[str, ...]:
        """This file's cells on the scan table, in column order."""
        return (
            self.path,
            str(self.chars),
            str(self.probes.gated_total),
            self.probes.watch_display,
            "|".join(self.probes.aliases) or "none",
            "PASS" if self.passed else "FAIL",
        )


class Scan(Table):
    """The scanned files side by side, measured into the table they print."""

    COLUMNS: ClassVar[tuple[tuple[str, bool], ...]] = (
        ("file", False),
        ("chars", True),
        ("gated", True),
        ("watch/1k", True),
        ("aliases", False),
        ("verdict", False),
    )
    """The scan table's headings in print order, each with whether its cells sit against the right edge."""

    @classmethod
    def of(cls, scans: Sequence[ProseScan]) -> Self:
        """Measure the scan table over the given files, in the order they are given in."""
        return cls.measured(cls.COLUMNS, [scan.cells for scan in scans])


class Comparison(BaseModel):
    """A candidate run measured against a baseline run."""

    model_config = ConfigDict(frozen=True)

    baseline_run: str
    candidate_run: str
    paired: bool
    """True when both runs share a plan fingerprint, so per-scene pairs are controlled."""
    scene_pairs: int
    scenes_shorter: int
    scenes_longer: int
    sign_test_p: float | None
    COLUMNS: ClassVar[tuple[tuple[str, bool], ...]] = (
        ("metric", False),
        ("baseline", True),
        ("candidate", True),
        ("change", True),
        ("verdict", False),
    )
    """The metric table's headings in print order, each with whether its cells sit against the right edge."""

    deltas: list[MetricDelta]
    new_gate_failures: list[GateFailure]
    fixed_gate_failures: list[GateFailure]
    verdict: Verdict

    @computed_field
    @property
    def p_value_display(self) -> str:
        """The sign-test p-value as the comparison header prints it; empty for an unpaired comparison."""
        return "" if self.sign_test_p is None else f"{self.sign_test_p:.3f}"

    @computed_field
    @property
    def table(self) -> Table:
        """The metric table: one row per delta, its columns measured across them."""
        return Table.measured(self.COLUMNS, [delta.cells for delta in self.deltas])
