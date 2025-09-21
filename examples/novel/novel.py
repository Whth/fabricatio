"""This module sets up a novel-writing workflow using the Fabricatio framework.

It initializes a role, registers a workflow for writing a novel, and dispatches the task.
"""

from fabricatio_core import Event, Role, Task
from fabricatio_novel.workflows.novel import WriteNovelWorkflow

# Initialize the role
(Role(name="writer").register_workflow(Event.quick_instantiate(ns := "write"), WriteNovelWorkflow).dispatch())


# Dispatch the task
path = (
    Task(
        name="write novel",
    )
    .update_init_context(
        novel_prompt="write a novel about a girl who discovers she has the ability to time travel, "
                     "but only to moments he has already lived through. 1 chap in total, 900 words."
    )
    .delegate_blocking(ns)
)
