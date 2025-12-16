"""CLI entry point."""
from enum import StrEnum

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from typer import Argument, Option, Typer
from typing import Dict

from pydantic import Field
from fabricatio_agent.actions.code import WriteCode, Architect
from fabricatio_core import Event, Role, Task, WorkFlow
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_team.models.team import Team



app = Typer()

class TaskType(StrEnum):
    """Task types."""
    CODING = "coding"
    ARCHITECT = "architect"
    


class Developer(Role, Cooperate):
    """A developer role."""

    registry: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: {
            Event.quick_instantiate(TaskType.CODING):
                WorkFlow(name="WriteCodeWorkFlow",
                         description="write the code according to you requirements with language and specification you provide, will return written code as string, will not write to disk.",
                         steps=(WriteCode().to_task_output(),)),
            Event.quick_instantiate(TaskType.ARCHITECT):
                WorkFlow(name="ArchitectWorkFlow",
                         description="If your task is too complex and need to break down into some smaller ones you should submit you task to this workflow.",
                         steps=(Architect().to_task_output(),)),
        },
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
    team = Team().join(Developer()).inform()
    team.dispatch()
    task = Task(name="Write code",description=prompt).update_init_context(enable_seq_thinking=sequential_thinking, prompt=prompt)
    codestr=task.delegate_blocking(TaskType.CODING)
    print(codestr)


if __name__ == "__main__":
    app()
