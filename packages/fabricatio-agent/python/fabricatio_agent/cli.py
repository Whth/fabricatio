"""CLI entry point."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from enum import StrEnum
from typing import Dict

from fabricatio_core import Event, Role, Task, WorkFlow
from fabricatio_core.rust import is_installed
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_team.models.team import Team
from pydantic import Field
from typer import Argument, Option, Typer

from fabricatio_agent.actions.code import CleanUp, Planning, WriteCode


class TaskType(StrEnum):
    """Task types."""

    Coding = "coding"
    Orchestrate = "orchestrate"
    CleanUp = "cleanup"
    Plot = "plot"
    Synthesize = "synthesize"
    Test = "test"
    Documentation = "documentation"


app = Typer()

dev_reg = {
    Event.quick_instantiate(TaskType.Coding): WorkFlow(
        name="WriteCodeWorkFlow",
        description="Generate desired code and then write that code to a file",
        steps=(WriteCode().to_task_output(),),
    ),
    Event.quick_instantiate(TaskType.CleanUp): WorkFlow(
        name="CleanWorkFlow",
        description="Clean unwanted files or directories.",
        steps=(CleanUp().to_task_output(),),
    ),
}

if is_installed("fabricatio_plot"):
    from fabricatio_plot.actions.fs import SaveDataCSV
    from fabricatio_plot.actions.plot import MakeCharts
    from fabricatio_plot.actions.synthesize import MakeSynthesizedData

    dev_reg.update(
        {
            Event.quick_instantiate(TaskType.Plot): WorkFlow(
                name="PlotWorkFlow",
                description="Generate plots and charts using matplotlib and save to fs.",
                steps=(MakeCharts().to_task_output(),),
            ),
            Event.quick_instantiate(TaskType.Synthesize): WorkFlow(
                name="SynthesizeWorkFlow",
                description="Synthesize data using synthesize data capabilities.",
                steps=(
                    MakeSynthesizedData(output_key="data_to_save"),
                    SaveDataCSV().to_task_output(),
                ),
            ),
        }
    )


class Developer(Role, Cooperate):
    """A developer role capable of handling coding tasks."""

    skills: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: dev_reg,
        frozen=True,
    )
    """The registry of events and workflows."""


class TestEngineer(Role, Cooperate):
    """A test engineer role for generating test cases."""

    skills: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: {
            Event.quick_instantiate(TaskType.Test): WorkFlow(
                name="GenerateTestcasesWorkFlow",
                description="Generate test cases for the given task.",
                steps=(WriteCode().to_task_output(),),
            )
        }
    )


class DocumentationWriter(Role, Cooperate):
    """A documentation writer role for writing documentation."""

    skills: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: {
            Event.quick_instantiate(TaskType.Test): WorkFlow(
                name="GenerateDocumentationWorkFlow",
                description="Generate documentation for the given task.",
                steps=(WriteCode().to_task_output(),),
            )
        }
    )


class ProjectLeader(Role, Cooperate):
    """A project leader role capable of handling planning tasks.

    This role implements the Cooperate capability and maintains a registry of workflows
    for different task types. The project leader can execute planning tasks through the
    PlanningWorkFlow which breaks down complex tasks into smaller subtasks.
    """

    skills: Dict[Event, WorkFlow] = Field(
        default_factory=lambda: {
            Event.quick_instantiate(TaskType.Orchestrate): WorkFlow(
                name="OrchestrateWorkFlow",
                description="This workflow is extremely expensive, so YOU SHALL use this as less as possible, you can use this only when necessary. Capable to finish task that is completely beyond your reach, but do add enough detailed context into task metadata. ",
                steps=(Planning().to_task_output(),),
            ),
        },
        frozen=True,
    )
    """The registry of events and workflows."""


@app.command(no_args_is_help=True)
def code(
    prompt: str = Argument(..., help="The prompt to generate code from."),
    sequential_thinking: bool = Option(
        False, "-sq", "--sequential-thinking", help="Whether to use sequential thinking."
    ),
) -> None:
    """Generate code based on the provided prompt.

    This function creates a development team with a Developer role and dispatches
    a coding task. If the task is complex, it will be broken down into smaller
    subtasks through the architect workflow.
    """
    Team().join(Developer()).join(ProjectLeader()).join(TestEngineer()).join(DocumentationWriter()).inform().dispatch()
    task = Task(name="Write code", description=prompt).update_init_context(sequential_thinking=sequential_thinking)
    task.delegate_blocking(TaskType.Orchestrate)


if __name__ == "__main__":
    app()
