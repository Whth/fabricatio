"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from typing import Optional

from fabricatio.capabilities.rag import RAG
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article, ArticleParagraphPatch
from fabricatio.models.utils import ok


class TweakArticleRAG(Action, RAG):
    """Write an article based on the provided outline."""

    output_key: str = "rag_tweaked_article"

    async def _execute(
        self, article: Article, collection_name: str = "article_essence", supervisor_check: bool = False, **cxt
    ) -> Optional[Article]:
        """Write an article based on the provided outline."""
        tweak_manual = ok(
            await self.draft_rating_manual(
                topic
                := "choose appropriate reference to insert into the article provided, "
                   "making article draw conclusion or reasoning based on concrete truth instead of unreliable subjective guessing"
            )
        )

        for _, __, subsec in article.iter_subsections():
            refind_q = ok(
                await self.arefined_query(
                    f"{article.referenced.as_prompt()}\n"
                    f"# Subsection whose content needs more reference to support it\n"
                    f"{subsec.display()}\n"
                    f"# Requirement\n"
                    f"search related article within the base to get some reference candidates to insert into the article, "
                    f"should prioritize using both the language of the original article and english"
                )
            )

            patch=ArticleParagraphPatch.default()
            patch.tweaked=subsec.paragraphs
            await self.correct_obj_inplace(
                patch,
                reference=await self.aretrieve_compact(refind_q),
                topic=topic,
                rating_manual=tweak_manual,
                supervisor_check=supervisor_check,
            )


