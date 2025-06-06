"""Example of using the library."""

from pathlib import Path

from fabricatio import Action, Event, Role, Task, WorkFlow
from fabricatio.capabilities import GenerateDeck
from fabricatio.models import Deck
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
    .register_workflow(Event.quick_instantiate(ns := "generate_deck"), WorkFlow(steps=(DeckGen().to_task_output(),)))
    .dispatch()
)

deck: Deck = ok(
    Task(name="gen deck")
    .update_init_context(
        source="topics.csv",
        req="为这个题库生成一个Anki Deck, 用户是中国大学生，需要有现代化的UI设计和交互，点击卡片后需要有动画效果，此外还需要有答题用时显示和答题正确率显示",
        output="here",
    )
    .delegate_blocking(ns)
)


compile_deck("here", f"{deck.name}.apkg")
