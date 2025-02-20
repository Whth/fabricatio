"""Actions that involve communication with the user."""

from fabricatio.models.action import Action
from fabricatio.models.task import Task


class Examining(Action):
    """Action that examines the input data."""

    name: str = "talk"
    output_key: str = "examine_pass"

    async def _execute(self, exam_target: Task[str], to_examine: str, **_) -> bool:
        """Examine the input data."""
        # TODO
