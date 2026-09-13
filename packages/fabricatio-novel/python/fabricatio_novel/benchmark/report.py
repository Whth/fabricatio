"""Render the benchmark reports through the shared handlebars store.

The scorer measures, and the models carry the printed form of every number a
report shows (the ``*_display`` computed fields).  This module only binds a
report template to one model dump, so every label, column and line break lives
in ``templates/built-in/bench_*.hbs`` and a report is rewritten without
touching Python.
"""

from collections.abc import Sequence

from fabricatio_core.rust import TEMPLATE_MANAGER

from fabricatio_novel.benchmark.models import Comparison, RunScorecard
from fabricatio_novel.config import novel_config


def render_scorecard(card: RunScorecard) -> str:
    """Render one run's scorecard."""
    return TEMPLATE_MANAGER.render_template(novel_config.bench_scorecard_template, card.model_dump(mode="json"))


def render_comparison(comparison: Comparison) -> str:
    """Render a candidate run against its baseline, one table row per metric."""
    return TEMPLATE_MANAGER.render_template(novel_config.bench_comparison_template, comparison.model_dump(mode="json"))


def render_board(cards: Sequence[RunScorecard]) -> str:
    """Render the runs as one table, in the order given."""
    return TEMPLATE_MANAGER.render_template(
        novel_config.bench_board_template, {"cards": [card.model_dump(mode="json") for card in cards]}
    )
