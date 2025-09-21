"""This module provides actions related to novel generation and management.

It includes classes such as GenerateNovel for creating novels based on prompts,
and DumpNovel for saving generated novels to a specified file path. These actions
leverage capabilities from the fabricatio_core and interact with both Python and
Rust components to perform their tasks.
"""

from pathlib import Path
from typing import Any, ClassVar, Optional

from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.rust import NovelBuilder


class GenerateNovel(NovelCompose, Action):
    """An action that generates a novel based on a provided prompt.

    This class inherits from NovelCompose and Action, and is responsible for
    generating a novel using the underlying novel generation capability.
    The generated novel is returned as a Novel object.
    """

    novel_prompt: Optional[str] = None
    """
    The prompt used to generate the novel. If not provided, execution will fail.
    """

    output_key: str = "novel"
    """
    The key under which the generated novel will be stored in the context.
    """

    ctx_override: ClassVar[bool] = True
    """
    Indicates that this action can override context values during execution.
    """

    async def _execute(self, **cxt) -> Novel | None:
        """Execute the novel generation process.

        Uses the provided novel_prompt to generate a novel via the inherited
        novel() method from NovelCompose. Returns the generated Novel object.

        Parameters:
            **cxt: Contextual keyword arguments passed from the execution environment.

        Returns:
            Novel | None: The generated novel object, or None if generation fails.
        """
        return await self.novel(ok(self.novel_prompt))


class DumpNovel(Action):
    """An action that saves a generated novel to a specified file path.

    This class takes a Novel object and writes its content to a file at the
    specified path. Currently, it prepares a NovelBuilder with the novel's
    title and chapters but does not yet persist the content to disk.
    """

    output_path: Optional[Path] = None
    """
    The file system path where the novel should be saved. Required for execution.
    """

    novel: Optional[Novel] = None
    """
    The novel object to be saved. Must be provided for successful execution.
    """

    output_key: str = "novel_path"
    """
    The key under which the output path will be stored in the context.
    """

    ctx_override: ClassVar[bool] = True
    """
    Indicates that this action can override context values during execution.
    """

    async def _execute(self, *_: Any, **cxt) -> Path:
        """Execute the novel dumping process.

        Validates the novel and path attributes, constructs a NovelBuilder with
        the novel's title and chapters, but currently returns the path without
        writing to disk as epub file.

        Parameters:
            *_: Ignored positional arguments.
            **cxt: Contextual keyword arguments passed from the execution environment.

        Returns:
            Path: The path where the novel was intended to be saved.

        Raises:
            ValueError: If novel or path is not provided (via ok() utility).
        """
        novel = ok(self.novel)
        path = ok(self.output_path)
        logger.info(f'Novel word count: [{novel.exact_word_count}/{novel.expected_word_count}] | Compliance ratio: {novel.word_count_compliance_ratio:.2%}')
        logger.info(f"Dumping novel {novel.title} to {path}")

        builder = (
            NovelBuilder()
            .new_novel()
            .set_title(novel.title)
            .set_description(novel.synopsis)
            .set_stylesheet("p { text-indent: 2em; margin: 1em 0; line-height: 1.5; text-align: justify; }")
        )

        for chapter in novel.chapters:
            builder.add_chapter(chapter.title, chapter.to_xhtml())

        builder.export(path)
        return path
