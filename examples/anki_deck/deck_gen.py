"""Example of using the library."""

from pathlib import Path

from fabricatio import Action, Event, Role, Task, WorkFlow
from fabricatio.capabilities import GenerateDeck
from fabricatio.models import Deck
from fabricatio_anki.actions.topic_analysis import AppendTopicAnalysis
from fabricatio_anki.rust import add_csv_data, compile_deck
from fabricatio_core import logger
from fabricatio_core.utils import ok


def get_column_names(csv_file_path: Path | str) -> list[str]:
    """Extract column names from a CSV file.

    Args:
        csv_file_path: Path to the CSV file

    Returns:
        List of column names
    """
    import csv

    with Path(csv_file_path).open(newline="", encoding="utf-8-sig") as csv_file:
        csv_reader = csv.reader(csv_file)
        # First row typically contains the column names
        return next(csv_reader)


class DeckGen(Action, GenerateDeck):
    """Generate a deck."""

    async def _execute(self, source: Path, req: str, output: Path, **cxt) -> Deck:
        names = get_column_names(source)
        logger.info(f"Column names: {names}")
        gen_deck = ok(await self.generate_deck(req, names, km=1, kt=1))

        gen_deck.save_to(output)
        add_csv_data(output, gen_deck.models[0].name, source)

        return gen_deck


(
    Role()
    .add_skill(Event.quick_instantiate(ns := "generate_deck"), WorkFlow(steps=(DeckGen().to_task_output(),)))
    .add_skill(
        Event.quick_instantiate(ns2 := "topic_analyze"),
        WorkFlow(steps=(AppendTopicAnalysis(csv_file="topics.csv").to_task_output(),)),
    )
    .dispatch()
)

requirement = (
    "Generate an Anki Deck for this question bank. The users are college students. "
    "The deck should have a modern UI design and interactive features, "
    "including animations when cards are clicked. Additionally, "
    "it should display the time taken to answer each question and the accuracy rate of the answers."
    "You Must use github-dark coloring for the UI design. dark mode should be enabled by default, do care about the font visibility."
)
deck: Deck = ok(
    Task(name="gen deck")
    .update_init_context(
        source="topics.csv",
        req=requirement,
        output="here",
    )
    .delegate_blocking(ns)
)

compile_deck("here", f"{deck.name}.apkg")

logger.info(f"Compiled deck saved to {deck.name}.apkg")

csv_output_path = ok(
    Task(name="analyze topics")
    .update_init_context(csv_file="topics.csv", output_file="topics_analyzed.csv")
    .delegate_blocking(ns2)
)


deck_with_analysis: Deck = ok(
    Task(name="gen deck with analysis")
    .update_init_context(source=csv_output_path, req=requirement, output="reformed")
    .delegate_blocking(ns)
)

compile_deck("here", f"{deck_with_analysis.name}.apkg")

logger.info(f"Compiled deck saved to {deck_with_analysis.name}.apkg")
