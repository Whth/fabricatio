"""Tests for the run-quality benchmark.

Every fixture is a synthetic staged run built from the pipeline's own context
models, so the benchmark is exercisable without a live LLM run: the metrics must
be provable on planted defects before they are trusted on a real corpus.
"""

import json
from pathlib import Path

import pytest
from _support import SceneSpec, StorySpec, benchmark_run
from fabricatio_core.rust import word_count
from fabricatio_novel.benchmark import (
    Gate,
    Metric,
    ProseScan,
    TermProbes,
    Verdict,
    compare,
    find_baseline,
    render_board,
    render_comparison,
    render_scan,
    render_scorecard,
    score_run,
    sign_test_p,
)
from fabricatio_novel.benchmark.models import StageArtifact
from fabricatio_novel.benchmark.text import cjk_ratio, sentences, significant_terms
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext

KEEPER = "The keeper rows out to the rocks."
"""Scene plan used by most fixtures; it names nothing a later scene would invent."""

ROWING_PROSE = "The keeper rows out to the rocks under a grey sky. The sea is quiet."
BELL_PROSE = "The lamp gutters once and a bell rings somewhere below the tower."
ECHO_TAIL = "The lamp gutters and the keeper counts the slow turn of the beam above the water."
"""A closing stretch the next scene can restage at its top — the seam echo defect."""

LONG_SENTENCE = "The keeper rows out to the rocks and counts the slow turn of the beam above the water."
"""A sentence past the long-sentence threshold, its closing period included."""


def _write_probes(root: Path, payload: dict[str, object]) -> Path:
    """Write a probe file the way a corpus would keep one and return its path."""
    path = root / "probes.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _story(
    rowing_prose: str = ROWING_PROSE,
    bell_prose: str = BELL_PROSE,
    docs: tuple[str, ...] = (),
) -> tuple[StorySpec, ...]:
    """Build the benchmark story: the plan text never changes, so prose is the only variable.

    Two runs built from this fixture share a plan fingerprint and therefore compare
    as paired samples, which is what the comparison tests need to exercise.
    """
    return (
        StorySpec(
            "Arrival",
            "The keeper leaves the lamp and rows out.",
            (
                SceneSpec("Rowing", KEEPER, rowing_prose),
                SceneSpec("The Bell", "The lamp gutters and a bell rings below.", bell_prose),
            ),
            docs=docs,
        ),
    )


def test_clean_run_passes_every_gate(tmp_path: Path) -> None:
    """A clean staged run scores green and reports its own shape."""
    card = score_run(benchmark_run(tmp_path, _story()))

    assert card.passed, card.gates_failed
    assert (card.chapters, card.scene_count, len(card.stories)) == (1, 2, 1)
    assert card.prose_words == word_count(f"{ROWING_PROSE}\n{BELL_PROSE}")
    assert card.target_words == sum(scene.target for scene in card.scenes)
    assert card.ratio == pytest.approx(card.prose_words / card.target_words)
    ratios = sorted(scene.words / scene.target for scene in card.scenes)
    assert card.scene_ratio_median == pytest.approx(ratios[1])
    assert card.scene_ratio_max == pytest.approx(ratios[-1])
    assert card.repetition.max_boundary_echo == 0.0
    assert card.prose.sentences.count == 3
    assert card.prose.vocabulary.grams > 0
    assert card.channel.docs_per_story == [0]
    assert card.integrity.concat_mismatches == []
    assert card.warnings == []
    assert "gates   PASS" in render_scorecard(card)


def test_seam_echo_is_reported_not_gated(tmp_path: Path) -> None:
    """A scene that opens by restaging the previous scene's closing stretch is flagged."""
    card = score_run(
        benchmark_run(
            tmp_path,
            _story(
                rowing_prose=f"The keeper rows out to the rocks. {ECHO_TAIL}",
                bell_prose=f"{ECHO_TAIL} The bell rings below the tower.",
            ),
        )
    )

    assert card.repetition.max_boundary_echo > 0.5
    loudest = max(card.repetition.boundary_echoes, key=lambda echo: echo.overlap)
    assert (loudest.scene, loudest.next_scene, loudest.title) == (1, 2, "Rowing")
    assert any("seam echo" in note for note in card.warnings)
    assert card.passed, "a seam echo is a warning: a refrain may repeat on purpose"


def test_verbatim_sentence_is_reported_not_gated(tmp_path: Path) -> None:
    """A sentence emitted in two scenes is reported, but refrains and catchphrases never fail a run."""
    echo = "The lamp gutters twice and goes out."
    card = score_run(
        benchmark_run(
            tmp_path,
            _story(
                rowing_prose=f"The keeper rows out to the rocks. {echo}",
                bell_prose=f"The bell rings below the tower. {echo}",
            ),
        )
    )

    assert [duplicate.scenes for duplicate in card.repetition.duplicate_sentences] == [[1, 2]]
    assert any("repeated verbatim" in note for note in card.warnings)
    assert card.passed


def test_sentence_lengths_are_measured(tmp_path: Path) -> None:
    """Sentence lengths are counted per sentence, and one past the threshold counts as long."""
    short = "Wait."
    card = score_run(benchmark_run(tmp_path, _story(rowing_prose=short, bell_prose=LONG_SENTENCE)))

    measured = card.prose.sentences
    assert (measured.count, measured.max_chars, measured.long_ratio) == (2, len(LONG_SENTENCE), 0.5)
    assert measured.mean_chars == pytest.approx((len(short) + len(LONG_SENTENCE)) / 2)


def test_vocabulary_repeats_are_measured(tmp_path: Path) -> None:
    """A run that recycles one phrase scores as more repetitive than a varied one."""
    phrase = "she looks away, "
    recycled = score_run(benchmark_run(tmp_path, _story(rowing_prose=phrase * 10, bell_prose=phrase * 10)))
    varied = score_run(
        benchmark_run(
            tmp_path,
            _story(
                rowing_prose=(
                    "the keeper rows out through the fog and counts the slow turn of the beam. "
                    "a bell rings somewhere below the tower, and the water keeps its own time. "
                    "he waits for the tide to turn before he speaks again."
                ),
                bell_prose="the harbour is quiet under a low grey sky, and the gulls have gone inland.",
            ),
            name="20260101-101010",
        )
    )

    assert recycled.prose.vocabulary.recycled_per_1k > varied.prose.vocabulary.recycled_per_1k
    assert max(tally.count for tally in recycled.prose.vocabulary.top) == 20


def test_directionless_metrics_report_drift(tmp_path: Path) -> None:
    """A metric with no better side reports an out-of-band move as drift, not as a regression."""
    baseline = score_run(
        benchmark_run(tmp_path, _story(rowing_prose="Wait.", bell_prose="Wait."), name="20260101-101010")
    )
    candidate = score_run(benchmark_run(tmp_path, _story(), name="20260101-111111"))

    verdicts = {delta.metric: delta.verdict for delta in compare(baseline, candidate).deltas}

    assert verdicts[Metric.SENTENCE_CHARS] == Verdict.DRIFTED
    assert verdicts[Metric.SENTENCE_VARIATION] == Verdict.DRIFTED


def test_reference_documents_are_counted(tmp_path: Path) -> None:
    """The channel row reports how many reference documents each story received, and their size."""
    document = "The lighthouse ledger lists every ship that passed the point."
    card = score_run(benchmark_run(tmp_path, _story(docs=(document,))))

    assert card.channel.docs_per_story == [1]
    assert card.channel.doc_chars == len(document)
    assert card.passed


def test_novel_reference_documents_are_counted(tmp_path: Path) -> None:
    """The channel row reports the novel's own documents before the per-story tally, and hides them without any."""
    document = "The lighthouse ledger lists every ship that passed the point."
    card = score_run(benchmark_run(tmp_path, _story(), novel_docs=(document,)))
    plain = score_run(benchmark_run(tmp_path, _story(), name="20260101-111111"))

    assert (card.channel.novel_docs, card.channel.novel_doc_chars) == (1, len(document))
    assert card.channel.docs_per_story == [0]
    assert f"channel novel 1 doc(s) {len(document)} chars, [0] docs/story, 0 chars" in render_scorecard(card)
    assert "channel [0] docs/story, 0 chars" in render_scorecard(plain)


def test_snapshot_reload_dispatches_by_data_shape(tmp_path: Path) -> None:
    """Snapshots whose stories carry retrieval settings reload rag-typed; plain snapshots stay plain."""
    run_dir = benchmark_run(tmp_path, _story())
    stages = {stage.name: stage for stage in StageArtifact.collect(run_dir)}

    assert type(stages["stage_06_story_plans"].load()) is NovelContext
    assert type(stages["stage_08_scenes"].load()) is RagNovelContext


def test_exported_text_mismatch_is_gated(tmp_path: Path) -> None:
    """An exported chapter that does not match the scenes fails the export gate."""
    run_dir = benchmark_run(tmp_path, _story())
    (run_dir / "chapters" / "01.txt").write_text("Something else entirely.", encoding="utf-8")

    card = score_run(run_dir)

    assert len(card.integrity.concat_mismatches) == 1
    assert Gate.EXPORT_TEXT in {failure.gate for failure in card.gates_failed}


def test_gated_probe_terms_fail_the_run(tmp_path: Path) -> None:
    """A gated term from a probe file that reaches the prose fails the run."""
    probes = TermProbes.load(_write_probes(tmp_path, {"gated": ["silver locket"]}))
    card = score_run(
        benchmark_run(
            tmp_path,
            _story(rowing_prose="The keeper rows out to the rocks. The silver locket stays shut."),
        ),
        probes=probes,
    )

    assert card.probes.gated == {"silver locket": 1}
    assert Gate.GATED_TERMS in {failure.gate for failure in card.gates_failed}


def test_watch_and_alias_mixing_are_reported(tmp_path: Path) -> None:
    """A watch term and two names used for one object are reported without failing the run."""
    probes = TermProbes(watch=frozenset({"silver"}), aliases=(("locket", "pendant"), ("boat", "skiff")))
    card = score_run(
        benchmark_run(
            tmp_path,
            _story(
                rowing_prose=(
                    "The keeper rows out to the rocks. The silver locket swings. The silver locket opens. "
                    "The pendant stays shut. The boat drifts past the point. Silver light on the water."
                )
            ),
        ),
        probes=probes,
    )

    assert card.probes.aliases == {"locket|pendant": {"locket": 2, "pendant": 1}}
    assert card.probes.watch_per_1k > 0.0
    assert "silver" in card.probes.watch_unlicensed
    assert card.passed


def test_probes_are_optional(tmp_path: Path) -> None:
    """Without a probe file a run scores on the corpus-independent metrics alone."""
    card = score_run(benchmark_run(tmp_path, _story()))

    assert not card.probes.configured
    assert card.probes.gated == {}
    assert "not configured" in render_scorecard(card)


def test_probes_resolve_to_the_project_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The table a project keeps in its working directory is the default source for every command."""
    (tmp_path / TermProbes.FILENAME).write_text(
        'gated = ["silver locket"]\nwatch = ["silver"]\naliases = [["locket", "pendant"]]\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    probes = TermProbes.resolve()

    assert probes is not None
    assert probes.gated == frozenset({"silver locket"})
    assert probes.watch == frozenset({"silver"})
    assert probes.aliases == (("locket", "pendant"),)


def test_probes_resolve_to_nothing_without_a_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A project that keeps no table leaves the probe rows unconfigured instead of failing."""
    monkeypatch.chdir(tmp_path)

    assert TermProbes.resolve() is None


def test_probes_skip_a_path_that_does_not_exist(tmp_path: Path) -> None:
    """A path that does not exist skips the probe rows instead of failing a command."""
    assert TermProbes.resolve(tmp_path / "absent.toml") is None


def test_explicit_probe_path_wins_over_the_project_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--probes`` beats the project's own table, whatever the working directory holds."""
    (tmp_path / TermProbes.FILENAME).write_text('gated = ["Gulls"]\n', encoding="utf-8")
    explicit = _write_probes(tmp_path, {"gated": ["silver locket"]})
    monkeypatch.chdir(tmp_path)

    probes = TermProbes.resolve(explicit)

    assert probes is not None
    assert probes.gated == frozenset({"silver locket"})


def test_scan_measures_prose_without_a_run(tmp_path: Path) -> None:
    """A manuscript with no run directory behind it measures the same term lists as a scored run."""
    draft = tmp_path / "draft.txt"
    draft.write_text("A locket lay beside a pendant; the Gulls took the silver.", encoding="utf-8")
    probes = TermProbes(gated=frozenset({"Gulls"}), watch=frozenset({"silver"}), aliases=(("locket", "pendant"),))

    scan = ProseScan.of(draft, probes)
    rendered = render_scan([scan])

    assert scan.probes.gated == {"Gulls": 1}
    assert scan.probes.watch == {"silver": 1}
    assert scan.probes.aliases == {"locket|pendant": {"locket": 1, "pendant": 1}}
    assert not scan.passed
    assert "draft.txt" in rendered
    assert "Gullsx1" in rendered
    assert "locket|pendant" in rendered


def test_compare_pairs_identical_plan_trees(tmp_path: Path) -> None:
    """Runs sharing a plan fingerprint compare per scene, and gates dominate the verdict."""
    probes = TermProbes.load(_write_probes(tmp_path, {"gated": ["Gulls"]}))
    baseline = score_run(benchmark_run(tmp_path, _story(), name="20260101-101010"), probes)
    candidate = score_run(
        benchmark_run(tmp_path, _story(rowing_prose=f"{ROWING_PROSE} Gulls."), name="20260101-111111"), probes
    )

    assert baseline.plan_fingerprint == candidate.plan_fingerprint
    result = compare(baseline, candidate)

    assert result.paired
    assert result.scene_pairs == 2
    assert result.verdict == Verdict.REGRESSED
    assert [failure.gate for failure in result.new_gate_failures] == [Gate.GATED_TERMS]
    by_metric = {delta.metric: delta for delta in result.deltas}
    assert by_metric[Metric.GATED_TERMS].verdict == Verdict.REGRESSED
    assert by_metric[Metric.DURATION_SECONDS].verdict == Verdict.NOISE
    assert "verdict regressed" in render_comparison(result)


def test_compare_calls_a_within_band_change_noise(tmp_path: Path) -> None:
    """A length change inside the noise band is not reported as a regression."""
    baseline = score_run(benchmark_run(tmp_path, _story(), name="20260101-101010"))
    candidate = score_run(benchmark_run(tmp_path, _story(ROWING_PROSE + " Gulls."), name="20260101-111111"))

    result = compare(baseline, candidate)

    assert result.paired
    verdicts = {delta.metric: delta.verdict for delta in result.deltas}
    assert verdicts[Metric.LENGTH_RATIO] == Verdict.NOISE
    assert verdicts[Metric.SCENE_RATIO_MAX] == Verdict.NOISE
    assert result.verdict == Verdict.UNCHANGED
    assert result.new_gate_failures == []


def test_find_baseline_prefers_the_same_plan_tree(tmp_path: Path) -> None:
    """The baseline search returns the newest earlier run that shares the plan tree."""
    benchmark_run(tmp_path, _story(), name="20260101-090000")
    matching = benchmark_run(tmp_path, _story(), name="20260101-100000")
    candidate = score_run(benchmark_run(tmp_path, _story(), name="20260101-110000"))

    baseline = find_baseline(candidate)

    assert baseline is not None
    assert baseline.run == matching.name
    assert baseline.plan_fingerprint == candidate.plan_fingerprint


def test_sign_test_p_values() -> None:
    """The paired sign test separates a lopsided change from a coin flip."""
    assert sign_test_p(0, 0) is None
    assert sign_test_p(1, 1) == pytest.approx(1.0)
    assert sign_test_p(8, 1) == pytest.approx(0.0390625)
    assert (sign_test_p(5, 5) or 0) > 0.05


def test_board_lists_scored_runs(tmp_path: Path) -> None:
    """The board names the runs it scored and marks their gate status."""
    score_run(benchmark_run(tmp_path, _story(), name="20260101-101010"))
    newest = score_run(benchmark_run(tmp_path, _story(), name="20260101-111111"))

    table = render_board([newest])

    assert "20260101-111111" in table
    assert "PASS" in table


def _assert_table_aligned(table: str) -> None:
    """Assert every pipe of a rendered table sits in the same column on every row."""
    lines = table.splitlines()
    rows = [line for line in lines if line.startswith("|")]
    assert len(rows) >= 3, f"no table to check:\n{table}"
    assert len(rows) == len([line for line in lines if "|" in line]), f"stray pipes beside the table:\n{table}"
    columns = {tuple(index for index, char in enumerate(row) if char == "|") for row in rows}
    assert len(columns) == 1, f"cells are not padded to a common width:\n{table}"
    assert rows[1].strip("|-") == "", "the rule row only separates the columns"


def test_compare_table_aligns_its_columns(tmp_path: Path) -> None:
    """Mixed-width metric names and deltas still line up as columns in a terminal."""
    baseline = score_run(benchmark_run(tmp_path, _story(), name="20260101-101010"))
    candidate = score_run(
        benchmark_run(tmp_path, _story(rowing_prose=f"{ROWING_PROSE} Gulls."), name="20260101-111111")
    )

    _assert_table_aligned(render_comparison(compare(baseline, candidate)))


def test_board_table_aligns_its_columns(tmp_path: Path) -> None:
    """Runs whose scores differ in width still line up as columns in a terminal."""
    widest = benchmark_run(
        tmp_path,
        _story(rowing_prose=f"The keeper rows. {ECHO_TAIL} Gulls above the water."),
        name="20260101-101010",
    )
    cards = [
        score_run(widest),
        score_run(benchmark_run(tmp_path, _story(), name="20260101-111111")),
    ]

    _assert_table_aligned(render_board(cards))


def test_terms_cover_both_scripts() -> None:
    """The term extractor yields Latin words and CJK character n-grams, with matching helpers.

    The CJK samples are code point escapes: the package ships no Chinese text and
    neither do its tests, so the non-Latin branch is exercised by code points
    instead of by embedding corpus material.
    """
    cjk_words = "\u6d4b\u8bd5\u6587\u672c"
    assert significant_terms("the silver locket") >= {"silver", "locket"}
    assert significant_terms(cjk_words) == {"\u6d4b\u8bd5\u6587", "\u8bd5\u6587\u672c", cjk_words}
    assert sentences("One. Two! Three\u3002") == ["One.", "Two!", "Three\u3002"]
    assert sentences("It cost 9.5 coins\u2026 and then it was gone.") == [
        "It cost 9.5 coins\u2026 and then it was gone."
    ]
    assert cjk_ratio("\u6d4b\u8bd5") == pytest.approx(1.0)
    assert cjk_ratio("plain") == 0.0
