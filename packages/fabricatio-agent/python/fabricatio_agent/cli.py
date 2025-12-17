"""CLI entry point."""

from enum import StrEnum

from fabricatio_actions.actions.fs import SmartDumpText
from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from typing import Dict

from fabricatio_core import Event, Role, Task, WorkFlow
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_team.models.team import Team
from pydantic import Field
from typer import Argument, Typer

from fabricatio_agent.actions.code import Architect, WriteCode

app = Typer()


class TaskType(StrEnum):
    """Task types."""

    CODING = "coding"
    ARCHITECT = "architect"


class Developer(Role, Cooperate):
    """A developer role."""

    registry: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: {
            Event.quick_instantiate(TaskType.CODING): WorkFlow(
                name="WriteCodeWorkFlow",
                description="Write the desired code to a SINGLE FILE in the file system according to you requirements with language and specification you provide, None will always be returned. "
                "Write one file at a time, You SHALL clearly describe the path to write. Also if you need to read some files you can specify their paths in the `dependencies` field of the task.",
                steps=(WriteCode(output_key="code"), SmartDumpText(text_key="code").to_task_output()),
            ),
            Event.quick_instantiate(TaskType.ARCHITECT): WorkFlow(
                name="ArchitectWorkFlow",
                description="If your task is too complex and need to break down into some smaller ones you should submit you task to this workflow.",
                steps=(Architect().to_task_output(),),
            ),
        },
        frozen=True,
    )
    """The registry of events and workflows."""


class QualityAssurance(Role, Cooperate):
    """A quality assurance role."""


@app.command()
def code(
    prompt: str = Argument(..., help="The prompt to generate the code."),
) -> None:
    """Generate a basic manifest of a standard rust project."""
    team = Team().join(Developer()).inform()
    team.dispatch()
    task = Task(name="Write code", description=prompt)
    task.delegate_blocking(TaskType.ARCHITECT)


if __name__ == "__main__":
    app()
