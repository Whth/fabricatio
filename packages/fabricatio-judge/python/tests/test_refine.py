"""Test the judged refine loop and its supporting models."""

from dataclasses import dataclass, field

import pytest
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import SketchedAble
from fabricatio_judge.capabilities.refine import RefineLoop
from fabricatio_judge.models.judgement import ImageVerdict, Verdict
from fabricatio_judge.models.refine import Attempt, AttemptHistory, RefinePlan

FEEDBACK_TEMPLATE = "test_refine_feedback"
"""Name of the stub feedback template installed by :func:`feedback_template_store`."""

_STUB_FEEDBACK_TEMPLATE = """\
{{#if history}}
## Previous Attempt Feedback
{{#each history}}
### Attempt {{@index}} (rejected)
- Prompt: {{this.prompt}}
- Defects: {{this.feedback}}
{{/each}}
{{/if}}
"""


@pytest.fixture(scope="module", autouse=True)
def feedback_template_store(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Install the stub feedback template so the loop can render its rejected-attempt tail."""
    test_dir = tmp_path_factory.mktemp("templates")
    (test_dir / f"{FEEDBACK_TEMPLATE}.hbs").write_text(_STUB_FEEDBACK_TEMPLATE)
    TEMPLATE_MANAGER.add_store(test_dir, rediscovery=True)


class FakeSpec(SketchedAble):
    """Minimal propose-able spec the loop revises."""

    prompt: str = ""


@dataclass(frozen=True)
class Artifact:
    """Minimal generated artifact."""

    tag: str


def verdict(passed: bool, feedback: str = "") -> ImageVerdict:
    """Build a one-word verdict carrying ``feedback`` as its defect list when failed."""
    return ImageVerdict(
        issue_to_judge="test",
        affirm_evidence=[],
        deny_evidence=[],
        final_judgement=passed,
        glitch_reasons=[] if passed else [feedback],
    )


class LoopRole(RefineLoop):
    """Role exposing the refine loop with ``propose`` patched per test."""


class GenFailedError(Exception):
    """Scripted generation failure."""


@dataclass
class ScriptedBench:
    """FIFO-scripted generate/judge bench recording every call."""

    artifacts: list[Artifact | None]
    verdicts: list[ImageVerdict | None]
    generated: list[str] = field(default_factory=list)
    """Prompts of every generation call, in call order."""

    judged: list[Artifact] = field(default_factory=list)
    """Artifacts handed to the judge, in call order."""

    archived: list[tuple[Artifact, int]] = field(default_factory=list)
    """Rejected artifacts with their 1-based attempt numbers."""

    async def generate(self, spec: FakeSpec) -> Artifact:
        """Consume the next scripted artifact; a scripted ``None`` raises ``GenFailedError``."""
        self.generated.append(spec.prompt)
        artifact = self.artifacts.pop(0)
        if artifact is None:
            raise GenFailedError("scripted generation failure")
        return artifact

    async def judge(self, artifact: Artifact) -> ImageVerdict | None:
        """Consume the next scripted verdict."""
        self.judged.append(artifact)
        return self.verdicts.pop(0)

    def plan(self) -> RefinePlan[FakeSpec, Artifact]:
        """Build the loop plan over this bench."""
        return RefinePlan(
            generate=self.generate,
            judge=self.judge,
            request_of=lambda artifact: f"prompt:{artifact.tag}",
            on_reject=lambda artifact, attempt: self.archived.append((artifact, attempt)),
            label="the unit",
        )


def patch_propose(monkeypatch: pytest.MonkeyPatch, revisions: list[FakeSpec | None]) -> list[str]:
    """Patch ``RefineLoop.propose`` to pop scripted revisions, recording every requirement."""
    requirements: list[str] = []

    async def fake_propose(cls: type[FakeSpec], requirement: str, **kwargs: object) -> FakeSpec | None:
        requirements.append(requirement)
        return revisions.pop(0) if revisions else None

    monkeypatch.setattr(RefineLoop, "propose", staticmethod(fake_propose))
    return requirements


async def test_accepts_first_attempt() -> None:
    """A passing verdict returns the first artifact after a single generation."""
    bench = ScriptedBench(artifacts=[Artifact("a1")], verdicts=[verdict(True)])
    role = LoopRole()

    out = await role.refine_until_accepted(
        FakeSpec,
        "base requirement",
        FakeSpec(prompt="v1"),
        bench.plan(),
        max_tries=3,
        feedback_template=FEEDBACK_TEMPLATE,
    )

    assert out == Artifact("a1")
    assert bench.generated == ["v1"]
    assert len(bench.judged) == 1
    assert bench.archived == []


async def test_revises_with_accumulated_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed verdict archives the artifact and re-proposes with the defect tail appended."""
    bench = ScriptedBench(
        artifacts=[Artifact("a1"), Artifact("a2")], verdicts=[verdict(False, "broken hands"), verdict(True)]
    )
    requirements = patch_propose(monkeypatch, [FakeSpec(prompt="v2")])
    role = LoopRole()

    out = await role.refine_until_accepted(
        FakeSpec,
        "base requirement",
        FakeSpec(prompt="v1"),
        bench.plan(),
        max_tries=3,
        feedback_template=FEEDBACK_TEMPLATE,
    )

    assert out == Artifact("a2")
    assert bench.generated == ["v1", "v2"]
    assert bench.archived == [(Artifact("a1"), 1)]
    assert len(requirements) == 1
    assert requirements[0].startswith("base requirement")
    assert "broken hands" in requirements[0]
    assert "prompt:a1" in requirements[0]


async def test_keeps_last_attempt_unjudged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exhausting the budget keeps the last artifact without judging it."""
    bench = ScriptedBench(artifacts=[Artifact("a1"), Artifact("a2")], verdicts=[verdict(False, "wrong hair")])
    patch_propose(monkeypatch, [FakeSpec(prompt="v2")])
    role = LoopRole()

    out = await role.refine_until_accepted(
        FakeSpec,
        "base requirement",
        FakeSpec(prompt="v1"),
        bench.plan(),
        max_tries=2,
        feedback_template=FEEDBACK_TEMPLATE,
    )

    assert out == Artifact("a2")
    assert bench.generated == ["v1", "v2"]
    assert len(bench.judged) == 1


async def test_clamps_budget_below_one() -> None:
    """A non-positive budget degrades to a single unjudged generation."""
    bench = ScriptedBench(artifacts=[Artifact("a1")], verdicts=[])
    role = LoopRole()

    out = await role.refine_until_accepted(
        FakeSpec,
        "base requirement",
        FakeSpec(prompt="v1"),
        bench.plan(),
        max_tries=0,
        feedback_template=FEEDBACK_TEMPLATE,
    )

    assert out == Artifact("a1")
    assert bench.generated == ["v1"]
    assert bench.judged == []


async def test_degrades_open_when_judge_unavailable() -> None:
    """A ``None`` verdict keeps the artifact without archiving it."""
    bench = ScriptedBench(artifacts=[Artifact("a1")], verdicts=[None])
    role = LoopRole()

    out = await role.refine_until_accepted(
        FakeSpec,
        "base requirement",
        FakeSpec(prompt="v1"),
        bench.plan(),
        max_tries=3,
        feedback_template=FEEDBACK_TEMPLATE,
    )

    assert out == Artifact("a1")
    assert bench.archived == []


async def test_generation_failure_propagates() -> None:
    """A failing first generation raises out of the loop without judging."""
    bench = ScriptedBench(artifacts=[None], verdicts=[])
    role = LoopRole()

    with pytest.raises(GenFailedError):
        await role.refine_until_accepted(
            FakeSpec,
            "base requirement",
            FakeSpec(prompt="v1"),
            bench.plan(),
            max_tries=3,
            feedback_template=FEEDBACK_TEMPLATE,
        )

    assert bench.judged == []


async def test_retry_generation_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing re-generation after a rejection raises out of the loop."""
    bench = ScriptedBench(artifacts=[Artifact("a1"), None], verdicts=[verdict(False, "blurry")])
    patch_propose(monkeypatch, [FakeSpec(prompt="v2")])
    role = LoopRole()

    with pytest.raises(GenFailedError):
        await role.refine_until_accepted(
            FakeSpec,
            "base requirement",
            FakeSpec(prompt="v1"),
            bench.plan(),
            max_tries=3,
            feedback_template=FEEDBACK_TEMPLATE,
        )

    assert bench.judged == [Artifact("a1")]


async def test_keeps_artifact_when_revision_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed revision proposal keeps the rejected artifact."""
    bench = ScriptedBench(artifacts=[Artifact("a1")], verdicts=[verdict(False, "blurry")])
    patch_propose(monkeypatch, [])
    role = LoopRole()

    out = await role.refine_until_accepted(
        FakeSpec,
        "base requirement",
        FakeSpec(prompt="v1"),
        bench.plan(),
        max_tries=3,
        feedback_template=FEEDBACK_TEMPLATE,
    )

    assert out == Artifact("a1")


def test_history_accumulates_and_renders_tail() -> None:
    """The history appends attempts and renders them through the feedback template."""
    history = (
        AttemptHistory()
        .with_attempt(Attempt(prompt="p1", feedback="f1"))
        .with_attempt(Attempt(prompt="p2", feedback="f2"))
    )

    tail = history.tail(FEEDBACK_TEMPLATE)

    assert "p1" in tail
    assert "f1" in tail
    assert "p2" in tail
    assert "f2" in tail
    assert AttemptHistory().tail(FEEDBACK_TEMPLATE) == ""


def test_image_verdict_is_a_verdict() -> None:
    """``ImageVerdict`` mixes in the nominal ``Verdict`` contract the loop consumes."""
    assert isinstance(verdict(True), Verdict)
    assert verdict(True).passed is True
    assert verdict(False, "broken hands").passed is False
    assert verdict(False, "broken hands").feedback == "broken hands"
