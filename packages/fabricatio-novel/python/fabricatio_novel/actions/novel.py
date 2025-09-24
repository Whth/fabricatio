"""This module provides actions related to novel generation and management.

It includes classes such as GenerateNovel for creating novels based on prompts,
and DumpNovel for saving generated novels to a specified file path. These actions
leverage capabilities from the fabricatio_core and interact with both Python and
Rust components to perform their tasks.
"""

from pathlib import Path
from typing import Any, ClassVar, List, Optional

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.novel import Novel, NovelDraft
from fabricatio_novel.models.scripting import Script
from fabricatio_novel.rust import NovelBuilder


class GenerateCharactersFromDraft(NovelCompose, Action):
    """Generate character cards from a NovelDraft."""

    novel_draft: Optional[NovelDraft] = None
    """
    The novel draft from which to generate characters.
    """

    output_key: str = "novel_characters"
    """
    Key under which the generated list of CharacterCard will be stored in context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[CharacterCard] | None:
        draft = ok(self.novel_draft, "`novel_draft` is required for character generation")
        logger.info(f"Generating characters for novel draft: '{draft.title}'")
        characters = await self.create_characters(draft)
        if characters is None:
            logger.warn("Character generation returned None.")
            return None
        valid_chars = [c for c in characters if c is not None]
        logger.info(f"Generated {len(valid_chars)} valid character(s).")
        return valid_chars


class GenerateScriptsFromDraftAndCharacters(NovelCompose, Action):
    """Generate chapter scripts from a draft and list of characters."""

    novel_draft: Optional[NovelDraft] = None
    """
    The novel draft containing chapter synopses.
    """

    novel_characters: Optional[List[CharacterCard]] = None  # ← renamed for clarity & collision avoidance
    """
    List of character cards to be used in script generation.
    """

    output_key: str = "novel_scripts"
    """
    Key under which the generated list of Script will be stored in context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[Script] | None:
        draft = ok(self.novel_draft)
        characters = ok(self.novel_characters)  # ← consume from context as "novel_characters"
        logger.info(f"Generating scripts for '{draft.title}' with {len(characters)} character(s).")
        scripts = await self.create_scripts(draft, characters)
        if scripts is None:
            logger.warn("Script generation returned None.")
            return None
        valid_scripts = [s for s in scripts if s is not None]
        logger.info(f"Generated {len(valid_scripts)} valid script(s).")
        return valid_scripts


class GenerateChaptersFromScripts(NovelCompose, Action):
    """Generate full chapter contents from scripts and characters."""

    novel_draft: Optional[NovelDraft] = None
    """
    The novel draft (for language, metadata).
    """

    novel_scripts: Optional[List[Script]] = None  # ← renamed
    """
    The list of chapter scripts to expand into full text.
    """

    novel_characters: Optional[List[CharacterCard]] = None  # ← renamed
    """
    The list of characters to provide context.
    """
    chapter_guidance: Optional[str] = None
    """
    Guidance for writing chapter.
    """

    output_key: str = "novel_chapter_contents"
    """
    Key under which the generated list of chapter content strings will be stored in context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> List[str] | List[str | None] | None:
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        characters = ok(self.novel_characters)

        logger.info(f"Generating {len(scripts)} chapter contents for '{draft.title}'.")
        chapter_contents = await self.create_chapters(draft, scripts, characters, self.chapter_guidance)
        if not chapter_contents:
            logger.warn("Chapter content generation returned empty or None.")
            return None
        logger.info(f"Successfully generated {len(chapter_contents)} chapter content(s).")
        return chapter_contents


class AssembleNovelFromComponents(NovelCompose, Action):
    """Assemble final Novel object from draft, scripts, and chapter contents."""

    novel_draft: Optional[NovelDraft] = None
    """
    The original draft containing title, synopsis, etc.
    """

    novel_scripts: Optional[List[Script]] = None  # ← renamed
    """
    Scripts containing chapter titles and metadata.
    """

    novel_chapter_contents: Optional[List[str]] = None  # ← renamed
    """
    Generated full text for each chapter.
    """

    output_key: str = "novel"
    """
    Key under which the assembled Novel object will be stored in context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> Novel:
        draft = ok(self.novel_draft)
        scripts = ok(self.novel_scripts)
        chapter_contents = ok(self.novel_chapter_contents)

        logger.info("Assembling final novel from components...")
        novel = self.assemble_novel(draft, scripts, chapter_contents)
        logger.info(f"Novel '{novel.title}' assembled with {len(novel.chapters)} chapters.")
        return novel


class ValidateNovel(Action):
    """Validate the generated novel for compliance and structure."""

    novel: Optional[Novel] = None
    """
    The novel to validate.
    """

    output_key: str = "novel_is_valid"
    """
    Key under which the validation result (bool) will be stored in context.
    """

    min_chapters: int = 1
    min_total_words: int = 1000
    min_compliance_ratio: float = 0.8

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> bool:
        novel = ok(self.novel)

        issues = []

        if len(novel.chapters) < self.min_chapters:
            issues.append(f"Too few chapters: {len(novel.chapters)} < {self.min_chapters}")

        if novel.exact_word_count < self.min_total_words:
            issues.append(f"Too few words: {novel.exact_word_count} < {self.min_total_words}")

        if novel.word_count_compliance_ratio < self.min_compliance_ratio:
            issues.append(
                f"Low compliance ratio: {novel.word_count_compliance_ratio:.2%} < {self.min_compliance_ratio:.2%}"
            )

        if issues:
            logger.warn(f"Novel validation failed for '{novel.title}': {'; '.join(issues)}")
            return False
        logger.info(f"Novel '{novel.title}' passed validation.")
        return True


class GenerateNovelDraft(NovelCompose, Action):
    """Generate a novel draft from a prompt."""

    novel_outline: Optional[str] = None
    """
    The prompt used to generate the novel. If not provided, execution will fail.
    """

    novel_language: Optional[str] = None
    """
    The language of the novel. If not provided, will infer from the prompt.
    """

    output_key: str = "novel_draft"
    """
    Key under which the generated NovelDraft will be stored in context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> NovelDraft | None:
        return await self.create_draft(outline=ok(self.novel_outline), language=self.novel_language)


class GenerateNovel(NovelCompose, Action):
    """An action that generates a novel based on a provided prompt.

    This class inherits from NovelCompose and Action, and is responsible for
    generating a novel using the underlying novel generation capability.
    The generated novel is returned as a Novel object.
    """

    novel_outline: Optional[str] = None
    """
    The prompt used to generate the novel. If not provided, execution will fail.
    """

    novel_language: Optional[str] = None
    """
    The language of the novel. If not provided, will infer from the prompt.
    """

    chapter_guidance: Optional[str] = None
    """
    Guidance for writing chapter.
    """

    output_key: str = "novel"
    """
    The key under which the generated novel will be stored in the context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, **cxt) -> Novel | None:
        """Execute the novel generation process.

        Uses the provided novel_prompt to generate a novel via the inherited
        novel() method from NovelCompose. Returns the generated Novel object.

        Parameters:
            **cxt: Contextual keyword arguments passed from the execution environment.

        Returns:
            Novel | None: The generated novel object, or None if generation fails.
        """
        return await self.compose_novel(ok(self.novel_outline), self.novel_language, self.chapter_guidance)


class DumpNovel(Action):
    """An action that saves a generated novel to a specified file path.

    This class takes a Novel object and writes its content to a file at the
    specified path.
    """

    output_path: Optional[Path] = None
    """
    The file system path where the novel should be saved. Required for execution.
    """

    novel_font_file: Optional[Path] = None
    """
    The file system path to the novel font file. like .ttf file.
    """

    novel: Optional[Novel] = None
    """
    The novel object to be saved. Must be provided for successful execution.
    """

    cover_image: Optional[Path] = None
    """
    The file system path to the novel cover image.
    """

    output_key: str = "novel_path"
    """
    The key under which the output path will be stored in the context.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt) -> Path:
        novel = ok(self.novel)
        path = ok(self.output_path)
        logger.info(
            f"Novel word count: [{novel.exact_word_count}/{novel.expected_word_count}] | Compliance ratio: {novel.word_count_compliance_ratio:.2%}"
        )
        logger.info(f"Novel Chapter count: {len(novel.chapters)}")
        logger.info(f"Dumping novel {novel.title} to {path}")

        builder = (
            NovelBuilder()
            .new_novel()
            .set_title(novel.title)
            .set_description(novel.synopsis)
            .add_css("p { text-indent: 2em; margin: 1em 0; line-height: 1.5; text-align: justify; }")
        )

        if self.novel_font_file:
            (
                builder.add_font(self.novel_font_file.stem, self.novel_font_file).add_css(
                    f"p {{ font-family: '{self.novel_font_file.stem}', 'sans-serif'; }}"
                )
            )

        if self.cover_image:
            builder.add_cover_image(self.cover_image.name, self.cover_image)

        for chapter in novel.chapters:
            builder.add_chapter(chapter.title, chapter.to_xhtml())

        builder.export(path)
        return path
