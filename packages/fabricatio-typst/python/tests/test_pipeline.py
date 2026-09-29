"""End-to-end tests for the staged article pipeline against a mock LLM router."""

from pathlib import Path
from uuid import uuid4

from fabricatio_core.models.action import OUTPUT_KEY, Action
from fabricatio_core.utils import ok
from fabricatio_mock import DUMMY_LLM_GROUP, MockScript, Value
from fabricatio_typst.models.article_proposal import ArticleProposal
from fabricatio_typst.models.context.article import ArticleContext
from fabricatio_typst.models.plan import ArticlePlan, ChapterPlan, SectionPlan, SubsectionPlan
from fabricatio_typst.workflows.article import ArticleWorkflow

CONSTRAINT = "Write for a methods-focused reader."

PROPOSAL = ArticleProposal(
    title="Sparse Supervision for Dense Depth",
    abstract="The paper argues that sparse LiDAR supervision suffices for dense monocular depth.",
    expected_word_count=600,
    focused_problem=["Sparse supervision leaves the far field unconstrained."],
    technical_approaches=["Scale-invariant loss with a normal-consistency term."],
    research_methods=["Train a depth network on 4% of the LiDAR points."],
    research_aim=["Recover dense depth without dense labels."],
    literature_review=["Monodepth2 (Godard et al., 2019)."],
    expected_outcomes=["A depth prior that transfers to unseen scenes."],
    keywords=["monocular depth", "self-supervision"],
)

ARTICLE_PLAN = ArticlePlan(
    heading="Sparse Supervision for Dense Depth",
    elaboration="The article argues that sparse supervision suffices for dense depth.",
    aims=["Frame the problem.", "Show the method.", "Report the results."],
    writing_styles=["lucid technical prose"],
    writing_constraints=["Cite only the retrieved references."],
    expected_word_count=600,
)

CHAPTER_PLAN = ChapterPlan(
    heading="Method",
    elaboration="Presents the scale-invariant training scheme.",
    aims=["Define the loss."],
    writing_styles=["first person plural"],
    writing_constraints=["Name every symbol before using it."],
)

SECTION_PLAN = SectionPlan(
    heading="Scale-invariant loss",
    elaboration="Derives the loss and its normal-consistency term.",
    aims=["Derive the loss."],
    writing_styles=[],
    writing_constraints=["State the loss once."],
)

SUBSECTION_PLANS = (
    SubsectionPlan(
        heading="Depth normalisation",
        elaboration="Introduces the scale-invariant normalisation.",
        aims=["Normalise the prediction per batch."],
        writing_styles=[],
        writing_constraints=["Keep the notation from the article plan."],
    ),
    SubsectionPlan(
        heading="Consistency term",
        elaboration="Adds the normal-consistency penalty.",
        aims=["Penalise normals that disagree."],
        writing_styles=["keep it short"],
        writing_constraints=["No new symbols."],
    ),
)

FIRST_PROSE = "Depth is normalised per batch, so scale cannot leak into the loss."
SECOND_PROSE = "The consistency term penalises normals that disagree with the image gradient."


def _pipeline_script() -> MockScript:
    """The replies a full staged run consumes, in call order."""
    return MockScript.from_values(
        Value.from_model(PROPOSAL, name="proposal"),
        Value.from_model(ARTICLE_PLAN, name="article plan"),
        Value.from_json([CHAPTER_PLAN.model_dump(by_alias=True)], name="chapter plans"),
        Value.from_json([SECTION_PLAN.model_dump(by_alias=True)], name="section plans"),
        Value.from_json([plan.model_dump(by_alias=True) for plan in SUBSECTION_PLANS], name="subsection plans"),
        Value.from_text(FIRST_PROSE, name="first subsection prose"),
        Value.from_text(SECOND_PROSE, name="second subsection prose"),
    )


NAMESPACE = "typst-staged-article"
"""Event namespace the runs of this module subscribe under."""

MOCKED = {"send_to": DUMMY_LLM_GROUP, "no_cache": True, "no_store": True}
"""Route every stage's calls to the dummy group, the only group the mock script answers.

The stages hand the task context's extra keys straight to their LLM calls, so the router
never reads — and never writes — the shared cache: a reply cached under the same prompt
bytes (a live run's, or an earlier test's) would otherwise be replayed instead of the
script, and the script's own replies would outlive the run. :func:`_briefing` adds the
other half: a run token that keeps every prompt's bytes unique.
"""


def _briefing() -> str:
    """Build one run's briefing, tokened so no two runs share prompt bytes."""
    return f"Recover dense depth from a single image using sparse LiDAR supervision. [run:{uuid4().hex[:8]}]"


async def _run_stages(
    cxt: dict[str, str | Path | bool | ArticleContext],
) -> dict[str, str | Path | bool | ArticleContext]:
    """Run every stage of the plain pipeline over one context dict, exactly as the workflow does."""
    for stage in ArticleWorkflow.iter_actions():
        assert isinstance(stage, Action)
        cxt = await stage.act(cxt)
    return cxt


async def test_article_workflow_plans_writes_and_dumps(tmp_path: Path) -> None:
    """Assert the staged run lands the whole tree, the running text and the dumped source."""
    out = tmp_path / "article.typ"
    briefing = _briefing()
    with _pipeline_script():
        cxt = await _run_stages(
            {
                **MOCKED,
                "article_briefing": briefing,
                "writing_constraint": CONSTRAINT,
                "article_output_path": out,
                "persist_dir": tmp_path / "persist",
            },
        )

    assert cxt[OUTPUT_KEY] == out
    text = out.read_text(encoding="utf-8")
    assert f"= {CHAPTER_PLAN.title}" in text
    assert FIRST_PROSE in text
    assert SECOND_PROSE in text

    ctx = cxt["article_ctx"]
    assert isinstance(ctx, ArticleContext)
    assert ctx.title == ARTICLE_PLAN.title
    assert ctx.expected_word_count == ARTICLE_PLAN.expected_word_count
    assert ctx.writing_constraints == ARTICLE_PLAN.writing_constraints

    chapters = ctx.child_contexts
    assert [chapter.title for chapter in chapters] == [CHAPTER_PLAN.title]
    sections = chapters[0].child_contexts
    assert [section.title for section in sections] == [SECTION_PLAN.title]
    leaves = sections[0].child_contexts
    assert [leaf.title for leaf in leaves] == [plan.title for plan in SUBSECTION_PLANS]

    assert [leaf.expected_word_count for leaf in leaves] == [300, 300]
    assert leaves[0].content == FIRST_PROSE
    assert leaves[1].content == SECOND_PROSE

    assert leaves[0].writing_styles == [*ARTICLE_PLAN.writing_styles, *CHAPTER_PLAN.writing_styles]
    assert leaves[1].writing_styles == [
        *ARTICLE_PLAN.writing_styles,
        *CHAPTER_PLAN.writing_styles,
        *SUBSECTION_PLANS[1].writing_styles,
    ]
    assert leaves[1].writing_constraints == SUBSECTION_PLANS[1].writing_constraints


async def test_content_stage_seeds_outline_and_running_text(tmp_path: Path) -> None:
    """Assert a subsection's requirement carries the planned outline and the prose written before it."""
    with _pipeline_script():
        cxt = await _run_stages({**MOCKED, "article_briefing": _briefing(), "persist_dir": tmp_path / "persist"})

    ctx = cxt["article_ctx"]
    assert isinstance(ctx, ArticleContext)
    leaves = ctx.child_contexts[0].child_contexts[0].child_contexts

    running = leaves[1].prefix_log.render()
    assert FIRST_PROSE in running, "the running text must carry the prose written before this subsection"
    assert SUBSECTION_PLANS[1].title in running, "the seeded outline must carry every planned heading"
    assert SECOND_PROSE not in running, "a written subsection's text must not drift after its write"


async def test_stage_snapshots_reload(tmp_path: Path) -> None:
    """Assert a stage's snapshot reloads as the same context tree the run built."""
    persist = tmp_path / "persist"
    briefing = _briefing()
    with _pipeline_script():
        cxt = await _run_stages({**MOCKED, "article_briefing": briefing, "persist_dir": persist})

    live = cxt["article_ctx"]
    assert isinstance(live, ArticleContext)
    assert live.briefing == briefing, (
        "the run's briefing reaches the context; it is a run-wide field, not a snapshot one"
    )

    reloaded = ok(
        ArticleContext.from_latest_persistent(persist / "stage_07_content"),
        "the content stage must leave a reloadable snapshot",
    )
    assert reloaded.title == ARTICLE_PLAN.title
    leaves = reloaded.child_contexts[0].child_contexts[0].child_contexts
    assert [leaf.content for leaf in leaves] == [FIRST_PROSE, SECOND_PROSE]
    assert [leaf.expected_word_count for leaf in leaves] == [300, 300]
