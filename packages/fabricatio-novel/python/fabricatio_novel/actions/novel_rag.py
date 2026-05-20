"""Novel RAG actions for retrieval-augmented generation."""

from typing import Any, ClassVar, List, Optional

from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.novel_rag import NovelComposeRAG, WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.scripting import Script


class RetrieveWritingStyles(NovelComposeRAG, Action):
    """Retrieve writing style documents from LanceDB based on a query."""

    writing_style_query: Optional[str] = None
    """The query text used to search for relevant writing style documents."""

    output_key: str = "writing_styles"
    """Key under which the retrieved writing style documents will be stored in context."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> List[WritingStyleDocument]:
        """Fetch writing style documents matching the query."""
        query = ok(self.writing_style_query, "`writing_style_query` is required for writing style retrieval")
        logger.info(f"Retrieving writing styles for query: {query[:100]}...")
        docs = list(ok(await self.afetch_document(query, WritingStyleFetchConfig.default())))
        logger.info(f"Retrieved {len(docs)} writing style document(s)")
        return docs


class InjectWritingStyleToScript(NovelComposeRAG, Action):
    """Inject retrieved writing style documents into scripts.

    Handles both script-level (global_prompt) and scene-level (per-scene prompt)
    injection. Script-level uses the provided `writing_styles`; scene-level fetches
    per-scene docs from LanceDB based on each scene's description.
    """

    novel_scripts: Optional[List[Script]] = None
    """The list of chapter scripts to augment with writing style guidance."""

    writing_styles: Optional[List[WritingStyleDocument]] = None
    """Global writing style documents to inject into each script's global_prompt."""

    output_key: str = "novel_scripts"
    """Key under which the augmented scripts will be stored in context (overwrites original)."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> List[Script]:
        """Inject writing styles into script-level and scene-level prompts."""
        scripts = ok(self.novel_scripts, "`novel_scripts` is required for writing style injection")
        global_docs = ok(self.writing_styles, "`writing_styles` is required for injection")
        config = WritingStyleFetchConfig.default()

        logger.info(f"Injecting {len(global_docs)} global writing style(s) into {len(scripts)} script(s)")

        for script in scripts:
            # Script-level: inject global writing styles
            for doc in global_docs:
                script.append_global_prompt(doc.as_prompt())

            # Scene-level: fetch per-scene based on each scene's description
            for scene in script.scenes:
                scene_docs: List[WritingStyleDocument] = list(
                    ok(await self.afetch_document(scene.description, config))
                )
                for doc in scene_docs:
                    scene.append_prompt(doc.as_prompt())

        logger.info("Writing style injection complete")
        return scripts
