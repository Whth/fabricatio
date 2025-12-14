"""CLI entry point."""

from typing import Dict

from fabricatio_core import Event, Role, Task, WorkFlow
from fabricatio_core.utils import cfg
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_team.models.team import Team
from pydantic import Field

from fabricatio_agent.actions.code import WriteCode

cfg(feats=["cli"])
from typer import Argument, Option, Typer

app = Typer()


class Developer(Role, Cooperate):
    """A developer role."""

    registry: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: {Event.quick_instantiate("coding"): WorkFlow(steps=(WriteCode().to_task_output(),))},
        frozen=True,
    )
    """The registry of events and workflows."""


class QualityAssurance(Role, Cooperate):
    """A quality assurance role."""


@app.command()
def code(
    prompt: str = Argument(..., help="The prompt to generate the code."),
    sequential_thinking: bool = Option(False, "--sqt", help="Whether to use sequential thinking."),
) -> None:
    """Generate a basic manifest of a standard rust project."""
    team = Team().join(Developer()).join(QualityAssurance()).inform()
    team.dispatch()
    task = Task(name="Write code").update_init_context(enable_seq_thinking=sequential_thinking, prompt=prompt)
    task.delegate_blocking("coding")


if __name__ == "__main__":
    app()
