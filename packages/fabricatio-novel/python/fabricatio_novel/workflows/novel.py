"""This module defines the WriteNovelWorkflow, which is responsible for generating and dumping a novel.

It utilizes the GenerateNovel action to create the novel content and DumpNovel to output it.
"""

from fabricatio_core import WorkFlow

from fabricatio_novel.actions.novel import DumpNovel, GenerateNovel

WriteNovelWorkflow = WorkFlow(
    name="WriteNovelWorkflow", description="Write a novel", steps=(GenerateNovel, DumpNovel().to_task_output())
)
