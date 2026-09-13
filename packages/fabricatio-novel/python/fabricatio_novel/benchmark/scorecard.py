"""Score one novel run directory against the run's own plan tree.

Everything measured here comes from artifacts the pipeline already persisted
(stage snapshots, chapter exports, the optional EPUB), so scoring a run never
calls an LLM and never re-executes anything. The plan tree is the ground truth:
a scene may use what its own plan and the prose before it license.

This module only sequences the factories its models carry: reading a run's files
belongs to ``StageArtifact``/``SceneRef`` and measuring what the run wrote to
``SceneScore.of``, ``RepetitionScore.of``, ``ProseScore.of`` and their siblings
(see ``benchmark/models.py``). How a measurement reads is the templates'
business (``templates/built-in/bench_*.hbs``, bound in ``benchmark/report.py``).

What this benchmark can and cannot measure, from calibrating it against audited
runs of a reference corpus:

* Measurable: verbatim sentence repeats, seam echoes (the same moment written at
  the end of one scene and again at the top of the next), sentence rhythm and
  vocabulary repeats (see ``ProseScore``), export integrity, script fidelity,
  length against target, cost, and — with a probe file — the term lists a corpus
  wants gated or watched (see ``probes``).
* NOT measurable from term statistics: staging the *next* scene's beats in the
  writer's own words. Every candidate rule tried during calibration fired either
  on every run or on none: the scenes of one novel share most of their vocabulary
  by construction, so overlap is not evidence, and deciding this takes a reader
  or a judge. Do not resurrect a term-overlap leak metric without one.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fabricatio_core.rust import word_count

from fabricatio_novel.benchmark.models import (
    ChannelScore,
    GateFailure,
    IntegrityScore,
    LanguageScore,
    ProbeScore,
    ProseScore,
    RepetitionScore,
    RunScorecard,
    SceneRef,
    SceneScore,
    StageArtifact,
    StoryScore,
)
from fabricatio_novel.benchmark.probes import TermProbes


def score_run(run_dir: Path, probes: TermProbes | None = None) -> RunScorecard:
    """Measure one run directory and return its scorecard.

    Supplying ``probes`` additionally measures the term lists a corpus wants
    gated or watched; without one every probe row reads as not configured.

    Raises ``FileNotFoundError`` when the directory holds no stage snapshots and
    ``ValueError`` when no snapshot carries composed prose — a run that never
    reached the writing stage cannot be scored.
    """
    stages = StageArtifact.collect(run_dir)
    if not stages:
        raise FileNotFoundError(f"no stage snapshots under {run_dir}")
    prose_stage = StageArtifact.newest_with_prose(stages)
    novel = prose_stage.load()
    refs = SceneRef.collect(novel)
    if not refs:
        raise ValueError(f"no scenes under {run_dir}")

    prose = "\n".join(ref.scene.content for ref in refs)
    scenes = [SceneScore.of(ref) for ref in refs]
    repetition = RepetitionScore.of(refs)
    prose_score = ProseScore.of(prose)
    channel = ChannelScore.of(novel, stages, prose_stage)
    integrity = IntegrityScore.of(run_dir, refs)
    language = LanguageScore.of(novel, prose)
    probe_score = ProbeScore.of(novel, prose, probes)

    prose_index = next(index for index, stage in enumerate(stages) if stage.path == prose_stage.path)
    plan_digests = "|".join(f"{stage.name}:{stage.digest}" for stage in stages[:prose_index])
    ratios = sorted(score.ratio for score in scenes if score.target > 0)
    target_words = novel.expected_word_count
    prose_words = word_count(prose)
    return RunScorecard(
        run=run_dir.name,
        run_dir=str(run_dir),
        scored_at=datetime.now(tz=UTC).astimezone(),
        started_at=min(stage.modified for stage in stages),
        duration_s=(max(stage.modified for stage in stages) - min(stage.modified for stage in stages)).total_seconds(),
        plan_fingerprint=hashlib.md5(plan_digests.encode("utf-8"), usedforsecurity=False).hexdigest()[:12],
        prose_fingerprint=prose_stage.digest,
        stages={stage.name: stage for stage in stages},
        chapters=len(novel.child_contexts),
        stories=StoryScore.from_scene_scores(scenes),
        scenes=scenes,
        scene_count=len(scenes),
        target_words=target_words,
        prose_words=prose_words,
        ratio=prose_words / target_words if target_words > 0 else 0.0,
        scene_ratio_median=ratios[len(ratios) // 2] if ratios else 0.0,
        scene_ratio_max=max(ratios, default=0.0),
        repetition=repetition,
        prose=prose_score,
        channel=channel,
        language=language,
        integrity=integrity,
        probes=probe_score,
        gates_failed=GateFailure.collect(language, integrity, probe_score),
        warnings=RunScorecard.warnings_of(scenes, repetition, probe_score),
    )
